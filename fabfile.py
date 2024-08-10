from fabric import task
from fabric import Connection
import io
import pathlib


@task
def setup_nodes(c):
	with open('./install.sh', mode='r') as file:
		c.run(file.read())


@task
def setup_external_node(c, internal_node_ip, v2ray_port=8081, recreate_stunnel_secret=False):
	assert '@' not in internal_node_ip
	# Setup stunnel
	secret = None
	try:
		secret = c.run('ls /etc/stunnel/stunnel.pem')
	except Exception as e:
		print(e)
	if secret is None or recreate_stunnel_secret:
		c.run('cd /etc/stunnel/')
		c.run('openssl genrsa -out stunnel.key 2048')
		c.run('openssl req -new -key stunnel.key -out stunnel.csr')
		c.run('openssl x509 -req -days 365 -in stunnel.csr -signkey stunnel.key -out stunnel.crt')
		c.run('cat stunnel.crt stunnel.key > stunnel.pem')
		with open('server.conf', 'r') as stunnel_server_conf:
			stunnel_server = stunnel_server_conf.read()
			stunnel_server = stunnel_server.replace('{V2RAY-PORT}', f'{v2ray_port}')
		with open('/tmp/server.conf', 'w') as file:
			file.write(stunnel_server)
		c.put('/tmp/server.conf', '/etc/stunnel/server.conf')
		c.sudo('systemctl restart stunnel4.service')
		c.run('systemctl status stunnel4.service')
	
	# Setup frpc
	path = c.run('pwd')
	base_path = pathlib.Path(path.stdout.strip())
	with open('./frpc.toml') as frpc_config:
		frpc_toml_conf = frpc_config.read()
		frpc_toml_conf = frpc_toml_conf.replace("{internal-node-ip}", f'{internal_node_ip}')
	with open('/tmp/frpc.toml', 'w') as file:
		file.write(frpc_toml_conf)
		
		relative = pathlib.Path('v2ray_setup/frp/frpc.toml')
		c.put('/tmp/frpc.toml', str(base_path / relative))
	with open('frp.service', 'r') as file:
		content = file.read()
		content = content.replace('{exec-start}',
		                          '{}/v2ray_setup/frp/frpc -c {}/v2ray_setup/frp/frpc.toml'.format(base_path,
		                                                                                           base_path))
	with open('/tmp/frpc.service', 'w') as file:
		file.write(content)
	c.put('/tmp/frpc.service', f'/etc/systemd/system/frpc-{internal_node_ip}.service')
	c.run(f'systemctl enable frpc-{internal_node_ip}.service')
	c.run(f'systemctl start frpc-{internal_node_ip}.service')


@task
def setup_internal_node(internal, external_address):
	with Connection(external_address) as external:
		stunnel_secret_result = external.run('cat /etc/stunnel/stunnel.pem')
		secret = stunnel_secret_result.stdout
		with open('/tmp/stunnel.pem', 'w') as file:
			file.write(secret)
	internal.sudo('chown -R $USER:$USER /etc/stunnel')
	internal.put('/tmp/stunnel.pem', '/etc/stunnel/stunnel.pem')
	internal.put('./client.conf', '/etc/stunnel/client.conf')
	internal.sudo('systemctl restart stunnel4')
	
	path = internal.run('pwd')
	base_path = pathlib.Path(path.stdout.strip())
	with open('frp.service', 'r') as file:
		content = file.read()
		content = content.replace('{exec-start}',
		                          '{}/v2ray_setup/frp/frps -c {}/v2ray_setup/frp/frps.toml'.format(base_path,
		                                                                                           base_path))
	with open('/tmp/frps.service', 'w') as file:
		file.write(content)
	internal.sudo('touch /etc/systemd/system/frps.service')
	internal.sudo('chown $USER:$USER /etc/systemd/system/frps.service')
	internal.put('/tmp/frps.service', '/etc/systemd/system/frps.service')
	internal.sudo('systemctl enable frps.service')
	internal.sudo('systemctl start frps.service')

#Todo, backup x-ui db
#Todo, add task to documentation