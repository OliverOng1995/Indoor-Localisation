import json
# import redis
import zmq
import time
import threading
import math
import random
import numpy as np
from collections import defaultdict
from datetime import timedelta
from shapely.geometry import Point
from shapely.geometry.polygon import Polygon
from operator import itemgetter
from pprint import PrettyPrinter

pp = PrettyPrinter(indent=2)

####################################################################################
## REDIS, ZMQ
####################################################################################

config  = None
with open('./aws_config.json', 'r') as f:
  config = json.load(f)

# print (config['zmqSockets']['broker']['xsub'])
# r = redis.Redis(charset="utf-8", decode_responses=True)

notifications = zmq.Context().socket(zmq.SUB)
notifications.setsockopt_string(zmq.SUBSCRIBE, config['notifications']['cacheUpdate'])
notifications.connect(config['zmqSockets']['broker']['xpub'])

notify = zmq.Context().socket(zmq.PUB)
notify.connect(config['zmqSockets']['broker']['xsub'])

# requests = zmq.Context().socket(zmq.REQ)
# requests.connect(config['zmqSockets']['serverRequests']['reqrep'])

####################################################################################
## State
####################################################################################

location = 'actlab'
cache         = {}
history       = defaultdict(lambda: {})
deviceId = 'b1'
sysStartTime = time.time()*1000
####################################################################################
## UTILITIES
####################################################################################

def updateCache():
  global cache
  cache = getCache()  
  print('loaded cache version', cache['version'])
  # requests.send_string(config['notifications']['cacheRequest'])
  # cache = requests.recv_json()
  # if cache and 'version' in cache:
    # print('loaded cache version', cache['version'])

####################################################################################
## Methods
####################################################################################

def augmentGraph(edges, interval):
  # augment info
  rems = []
  for t in edges:
    for r in edges[t]:
      try:
        measuredPower = float(cache['devices'][t]['beacon']['measuredPower'])
        rssi          = float(edges[t][r]['mu'])
        sigma         = float(edges[t][r]['sigma'])
        period        = float(edges[t][r]['period'])
        location      = cache['devices'][r]['location']
        sigmaDistance = rssiToDistanceVariance(rssi, sigma, measuredPower)
        distance      = rssiToDistance(rssi, measuredPower)
        scale         = location['map']['scale']
        sigmaRadians  = sigmaDistance / scale**2
        edges[t][r] = {
          'measuredPower': measuredPower,
          'rssi': rssi,
          'sigma': sigma,
          'numObservations': interval / period,
          'location': location,
          'distance': distance,
          'sigmaDistance': sigmaDistance,
          'radians': distance / scale,
          'sigmaRadians': sigmaRadians
        }
      except:
        rems.append((t,r))
        continue

  # remove malformed edges
  for (t, r) in rems:
    del edges[t][r]

  # get edges not in the same map as closest
  rems = []
  for t, info in edges.items():
    try:
      if info:
        closest   = sorted(info.keys(), key=lambda r: info[r]['distance'])[0]
        location  = info[closest]['location']
        for r in info:
          if info[r]['location']['map']['id'] != location['map']['id']:
            rems.append((t,r))
    except:
      continue

  # remove receivers not in the same map as the closest
  for (t, r) in rems:
    del edges[t][r]

  # return augmented edges
  return edges

def transmitterGraph(edges):
  d = defaultdict(lambda: {})
  for k, v in edges.items():
    receiverId      = v['receiverId']
    transmitterId   = v['transmitterId']
    beaconId        = cache['device'][transmitterId]['beaconId']
    measuredPower   = float(cache['beacon'][beaconId]['measuredPower'])
    rssi            = float(v['mu'])
    mapId           = cache['device'][receiverId]['mapId']
    scale           = float(cache['map'][mapId]['scale']) 
    distance        = rssiToDistance(rssi, measuredPower)
    # make dictionary
    d[transmitterId][receiverId] = {
      'distance': distance,
      'radians':  distance / scale,
      'scale':    scale,
      'lat':      float(cache['device'][receiverId]['lat']),
      'lng':      float(cache['device'][receiverId]['lng']),
      'mapId':    mapId
    }
  # remove nodes which are not in the same map as the closest node
  remove = set()
  for t in d.keys():
    closest = sorted(d[t].keys(), key=lambda x: d[t][x]['distance'])[0]
    mapId   = d[t][closest]['mapId']
    for r, v in d[t].items():
      if v['mapId'] != mapId:
        remove.add((t,r))
  # delete entries
  for (t, r) in remove:
    del d[t][r]
  return d

def calculateLocation(n, nbrsInfo):
  nbrs  = list(nbrsInfo.keys())
  _map        = nbrsInfo[nbrs[0]]['location']['map']
  pos   = barycentric(
    n,
    nbrs,
    nbrsInfo
  )
  return {
    'map': _map,
    'latLng': pos,
    'lat': pos[1,0],
    'lng': pos[0,0]
  }

def transmitterLocations(transmitters):
  return { t: calculateLocation(t, info) \
    for t, info in transmitters.items() \
    if cache['devices'][t]['type'] == 'mobile' and info}

def distance(a, b, scale):
  return scale * np.linalg.norm(a - b)

def updateLocations(locations, delta):
  global history
  updates = set()
  for deviceId, location in locations.items():
    _map = location['map']
     # create if not exist
    if (deviceId not in history) or \
    (deviceId in history and \
    distance(location['latLng'], history[deviceId]['location']['latLng'], _map['scale']) > delta):
      updates.add(deviceId)
    # update history
    history[deviceId].update({
      'location': {
        'map': _map,
        'latLng': location['latLng'],
        'lat': location['lat'],
        'lng': location['lng']
      }
    })
  return updates

def between_decimals(min, max): 
  return random.uniform(min, max)


def processEdges(interval):
  now           = int(time.time() * 1000)
  try:
    _map = {
        "id": location,
          "coordinates": [
          [
            -0.11997600023306632,
            0.2390170498225217
          ],
          [
            0.36101917799351213,
            0.2390170498225217
          ],
          [
            0.36101917799351213,
            -0.028774003760801747
          ],
          [
            -0.11997600023306632,
            -0.028774003760801747
          ]
        ],
        "scale": 52
    }

    lng = between_decimals(-0.11997600023306632,0.36101917799351213)
    lat = between_decimals(-0.028774003760801747,0.2390170498225217)

    deviceId = 'b1'

    print ("Sending position data...")
    topic = config['notifications']['positionUpdate']
    message = json.dumps({
        'id':     deviceId,
        'lng':    lng,
        'lat':    lat,
        'map':    _map,
        'time':   now
      })
    print (message)
    notify.send_multipart([topic.encode('utf-8'), message.encode('utf-8')])
    print ('================================================================')
  except: raise

####################################################################################
## THREADS
####################################################################################

def listenForCacheUpdates():
  global cache
  while True:
    [topic, message] = notifications.recv_multipart()
    message = json.loads(message.decode())
    if message['version'] != cache['version']:
      updateCache()

def main():
  interval = 2000
  i = 0
  start = sysStartTime
  timer = time.time()*1000
  exit = sysStartTime + 20000
  while timer < exit:
    while math.floor(timer-start) == 5:
      start+=interval
      try:
          processEdges(interval*1000)
          timer = time.time()*1000
      except:
        raise
      i+=1
    timer = time.time()*1000

####################################################################################
## BEGIN
####################################################################################

# update cache
# updateCache()

# listen for cache notifications
# t1 = threading.Thread(target=listenForCacheUpdates)
# t1.setDaemon(True)
# t1.start()

# main loop
main()
