#!/bin/bash

cd /home/pi/python/PoolSurvey;
if [ -d /home/pi/python/PoolSurvey/PoolSurvey_new ]; then
	cp /media/pi/data/database.ini /home/pi/python/PoolSurvey/PoolSurvey;
	if [ -f /home/pi/python/PoolSurvey/PoolSurvey_new/update.py ]; then
		mv /home/pi/python/PoolSurvey/PoolSurvey_new/update.py /home/pi/python/PoolSurvey/;
		python /home/pi/python/PoolSurvey/PoolSurvey_new/update.py /media/pi/data database.ini;
	fi
	echo "Switch to new server version.";
	mv /home/pi/python/PoolSurvey/PoolSurvey /home/pi/python/PoolSurvey/PoolSurvey_bak;
	mv /home/pi/python/PoolSurvey/PoolSurvey_new /home/pi/python/PoolSurvey/PoolSurvey;
else
	if [ -d /home/pi/python/PoolSurvey/PoolSurvey_bak ]; then
		echo "Restore previous version because the new server version had not started!";
		rm -frd /home/pi/python/PoolSurvey/PoolSurvey;
		mv /home/pi/python/PoolSurvey/PoolSurvey_bak /home/pi/python/PoolSurvey/PoolSurvey;
		mv /home/pi/python/PoolSurvey/PoolSurvey/database.ini /media/pi/data/;
		sudo reboot;
	fi
fi
cd /home/pi/python/PoolSurvey/PoolSurvey;
echo "Start server...";
python /home/pi/python/PoolSurvey/PoolSurvey/server.py;

 

