# whereareyou
Inspired by [whereami](https://github.com/kootenpv/whereami). Passive indoor localization using the Wifi signal strength of a users devices. A set of slaves (like Raspberry Pis) is distributed at the location and send the signal strengths of detected devices to a master server. Based on a pretrained model the master predicts where the devices currently are located.

## Setup

- Install Cython  
`apt-get install cython`
- Install Python dependencies  
`pip install -r requirements.txt`

### Slaves
- Install aircrack-ng  
`apt-get install aircrack-ng`  
- Set your Wifi interface to monitor mode e.g.  
`airmon-ng start wlp3s0`

### Master  
- Copy `example.env` to `.env` and add the appropriate configuration keys  
`cp example.env .env`
- Adapt `static/office.svg` and `static/office_mapping.json` to your office (we recommend [this](http://editor.method.ac/) online editor). You can test your office mapping at /test_mapping.
- Create the database initially  
`python -c "from master import db, load_locations; db.create_all(); load_locations()"`  


## Usage
### Slaves
- Run `slave.py` on every device at the location you're owning  
`python slave.py --network ItHurtsWhenIP --wifi-interface mon0 --master-address https://192.168.0.2:5000 --slave-id MySlaveId`  

### Master
- Run `master.py` on a device that can be accessed by the slaves in your internal network  
`python master`  
