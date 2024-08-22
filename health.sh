#!/bin/bash
# Please define an http proxy on xui pannel for this reason
hstatus=$(curl 'https://www.whatsapp.com' --proxy "http://{user}:{password}@{host}:{port}" --max-time 15 -s -o /dev/null -w "%{http_code}")
echo $hstatus

start_time=$(date +%s.%N)


end_time=$(date +%s.%N)

duration=$(echo "$end_time - $start_time" | bc)

echo "Duration: $duration seconds to fetch"

if [ "$hstatus" -eq 200 ]; then
	echo "Whatsapp web fetched successfully";
else
	echo "Service is down or has been censored";
	echo "Going to restart frpc*";
	systemctl restart frpc*;
	echo "Going to restart stunnel";
	systemctl restart stunnel*;
	echo "Going to restart x-ui.service";
	systemctl restart x-ui.service;
	echo "Going to restart ns2.ns2ns2.com frps, x-ui, stunnel services";
	ssh {user}@{host} "sudo systemctl restart frps.service"
	ssh {user}@{host} "sudo systemctl restart x-ui.service"
	ssh {user}@{host} "sudo systemctl restart stunnel4.service"
	echo "Done"

fi

