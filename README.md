# whereareyou
Passive indoor localization using the Wifi signal strength of a users devices. A set of slaves (like Raspberry Pis) are distributed at the location and send the signal strengths of detected devices to a master server. Based on a pretrained model the master predicts where the devices currently are located.

## Setup
- Install aircrack-ng  
`apt-get install aircrack-ng`  
- Set your Wifi interface to monitor mode e.g.  
`airmon-ng start wlp3s0`
- Install Python dependencies  
`pip install -r requirements.txt`  
- Run `slave.py` on every device at the location you're owning  
`python slave.py`  
