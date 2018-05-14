#!/bin/bash
ref_path='/home/pi/python'
data_path='/media/pi/data'
cd $ref_path
# Check if an update is needed
if [ -d $ref_path/PoolSurvey_new ]; then
    # Save database file first for a next restoration
    echo "Installing new version..."
    logger -t PoolManager Installing new version
    cp -f $data_path/database.ini $ref_path/PoolSurvey
    # If few treatments are necessary do them
    if [ -f $ref_path/PoolSurvey_new/update.py ]; then
        echo "Do a special update..."
        logger -t PoolManager Do a special update
        mv $ref_path/PoolSurvey_new/update.py $ref_path
        python $ref_path/update.py $ref_path $data_path database.ini
        rm -f $ref_path/update.py
    fi
    # Switch to new server version but keep old in case of...
    mv $ref_path/PoolSurvey $ref_path/PoolSurvey_bak
    mv $ref_path/PoolSurvey_new $ref_path/PoolSurvey
else
    # If after a reboot, an old version is detected restore it
    if [ -d $ref_path/PoolSurvey_bak ]; then
        # Restore previous version because the new server version had not started!
        echo "Previous version restored!"
        logger -t PoolManager Previous version restored
        rm -frd $ref_path/PoolSurvey
        mv $ref_path/PoolSurvey_bak $ref_path/PoolSurvey
        mv $ref_path/PoolSurvey/database.ini $data_path
        reboot
    fi
fi
cd $ref_path/PoolSurvey
chmod +x startup.sh
# -g means BCM
gpio -g mode 16 up
state=`gpio -g read 16`
if [ "$state" = "0" ]; then
    echo "Start server..."
    logger -t PoolManager Start server
    python server.py $ref_path $data_path database.ini
else
    echo "Autostart disabled!"
    logger -t PoolManager Autostart disabled
fi

