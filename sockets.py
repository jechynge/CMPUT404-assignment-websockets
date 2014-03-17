#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle, Jordan Ching
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

# Shamelessly ripped from the in-class examples. If it ain't broke etc etc.
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()
myClients = list()

def set_listener( entity, data ):
    msg = json.dumps({entity:data})
    for client in myClients:
        client.put(msg)

myWorld.add_set_listener( set_listener )

# Also re-purposed from the in-class examples.
def read_ws(ws,client):
    '''A greenlet function that reads from the websocket'''
    try:
        while True:
            msg = ws.receive()
            if (msg is not None):
                if(msg != "null"):
                    entities = json.loads(msg)
                    for i in entities:
                        myWorld.set(i, entities[i])
            else:
                break
    except:
        '''Done'''

# Also re-purposed from the in-class examples.
@sockets.route('/subscribe')
def subscribe_socket(ws):
    client = Client()
    myClients.append(client)
    g = gevent.spawn( read_ws, ws, client )
    try:
        client.put(json.dumps(myWorld.world()))
        while True:
            msg = client.get()
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print "WS Error %s" % e
    finally:
        myClients.remove(client)
        gevent.kill(g)

def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

@app.route("/")
def hello():
    return flask.redirect('/static/index.html')

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    updateEntity = flask_post_json()
    for key in updateEntity:
        myWorld.update(entity, key, updateEntity[key])
    
    return flask.jsonify(myWorld.get(entity))

@app.route("/world", methods=['POST','GET'])
def world():
    if(request.method == 'POST'):
        entities = flask_post_json()
        for i in entities:
            myWorld.set(str(random.randint(1,1000000)), entities[i])
    
    return flask.jsonify(myWorld.world())

@app.route("/seeTheWorld", methods=['GET'])
def seeTheWorld():
    html = "<!DOCTYPE html><head><title>World Representation</title></head><body>"
    html += "<h1>World Representation</h1>"
    html += "<table><thead><th>Name</th><th>X</th><th>Y</th><th>Colour</th></thead>"
    html += "<tbody>"
    entities = myWorld.world()
    for entity in entities:
        myEntity = entities[entity]
        html += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (entity, myEntity["x"], myEntity["y"], myEntity["colour"])
    
    html += "</tbody></table></body></html>"
    
    return html

@app.route("/entity/<entity>")    
def get_entity(entity):
    return flask.jsonify(myWorld.get(entity))

@app.route("/clear", methods=['POST','GET'])
def clear():
    myWorld.clear()
    for client in myClients:
        client.put(json.dumps({'SRVRCTRL':'CLEAR'}))
    return "World cleared."



if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
