from flask import Flask, render_template, request
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer
import gevent
import dbus, json, time, thread
from collections import deque

app = Flask(__name__)
q = deque()
active = True
app.debug = True
session_bus = dbus.SessionBus()
player = session_bus.get_object('org.mpris.clementine', '/Player')
iface = dbus.Interface(player, dbus_interface='org.freedesktop.MediaPlayer')
last = None
status = None

def getMeta():
    res = {}
    for k, v in dict(iface.GetMetadata()).items():
        res[str(k)] = str(v)
    return res

@app.route("/")
def routeIndex():
    return render_template('index.html', song=dict(iface.GetMetadata()), playing=not bool(int(iface.GetStatus()[0])))

@app.route('/getimage')
def routeGetImage():
    return open(str(dict(iface.GetMetadata())['arturl']).split('file://')[-1], 'rb').read()

@app.route("/pause")
def routePause():
    iface.Pause()
    return True

@app.route("/play")
def routePlay():
    iface.Play()
    return True

def recv_thread(args):
    global active
    while active:
        message = args[0].receive()
        if message == None:
            active = False
            return
        elif message == "pause": iface.Pause()
        elif message == "play": iface.Play()
        elif message == "last": iface.Prev()
        elif message == "next": iface.Next()

@app.route('/api')
def api():
    global last, status
    if request.environ.get('wsgi.websocket'):
        ws = request.environ['wsgi.websocket']
        gevent.spawn(recv_thread, (ws, ))
        while active:
            gevent.sleep(.5)
            v = not bool(int(iface.GetStatus()[0]))
            # Lets get the percentage we're at
            meta = getMeta()
            perc = (float(iface.PositionGet())/float(meta['mtime']))*100
            ws.send(json.dumps({'tag': 'bar', 'value': perc}))

            #Do we need to update song info?
            if meta['title'] == last and status == v: continue
            else:
                last = meta['title']
                status = v
                t = str(float(meta['time'])/float(60)).split('.', 1)
                s = str(float('.'+t[1])*60).split('.')[0]
                meta['time'] = '%s:%s' % (t[0], s)
                ws.send(json.dumps({'tag': 'update', 'playing': v, 'meta': meta}))
    return "Bewbs :3"
if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    http_server.serve_forever()
