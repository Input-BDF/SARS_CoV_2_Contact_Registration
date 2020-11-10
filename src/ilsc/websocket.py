# -*- coding: utf-8 -*-
'''
Created on 06.06.2020

@author: Input
'''

__all__ = ['WebsocketMultiServer']
from autobahn.twisted.websocket import WebSocketServerFactory, \
    WebSocketServerProtocol, ConnectionDeny

class WSServerProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        try:
            cookie = request.headers['cookie']
            auth = self.factory.connection_made(cookie)
            if auth:
                self.factory.register_client(self)
            else:
                #TODO: maybe implement this somehow with raise ConnectionDeny
                self.failHandshake(403, 'Wrong server dude')
        except Exception as e:
            self.failHandshake(500, 'Something went wrong')

    def connectionLost(self, reason):
        self.factory.connection_lost(reason)
        self.factory.unregister_client(self)

    def onMessage(self, payload, isBinary):
        response, isBinary = self.factory.callback(payload, isBinary)
        if response != False:
            self.factory.communicate(self, response, isBinary)
        
class WebsocketMultiServer(WebSocketServerFactory):
    protocol = WSServerProtocol

    def __init__(self, *args, **kwargs):
        super(WebsocketMultiServer, self).__init__(*args, **kwargs)
        self.clients = {}
        self.callback = None
        self.connection_made = None
        self.connection_lost = None

    def set_backend_connections(self, bck_end_callback = None, bck_end_connection_made=None, bck_end_connection_lost=None):
        self.callback = bck_end_callback
        self.connection_made = bck_end_connection_made
        self.connection_lost = bck_end_connection_lost

    def register_client(self, client):
        self.clients[client.peer] = {"object": client}

    def unregister_client(self, client):
        try:
            self.clients.pop(client.peer)
        except KeyError:
            pass

    def communicate(self, client, payload, isBinary):
        try:
            client.sendMessage(payload.encode('utf-8'))
        except Exception as e:
            print(e)
    
    def broadcast(self, payload, isBinary):
        for client in self.clients:
            self.communicate(self.clients[client]['object'], payload, isBinary)
