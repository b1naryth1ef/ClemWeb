from flask import Flask, render_template, request, session
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer
import gevent
import dbus, json, time, thread
from collections import deque

app = Flask(__name__)
q = deque()
active = True
app.debug = True
app.secret_key = "so_secret"
session_bus = dbus.SessionBus()
player = session_bus.get_object('org.mpris.clementine', '/Player')
tracks = session_bus.get_object('org.mpris.clementine', '/TrackList')
iface = dbus.Interface(player, dbus_interface='org.freedesktop.MediaPlayer')
def getMeta():
    res = {}
    for k, v in dict(iface.GetMetadata()).items():
        res[str(k)] = v #.encode('ISO-8859-1')
    return res

@app.route("/")
def routeIndex():
    return render_template('index.html')

@app.route('/getimage')
def routeGetImage():
    return open(str(dict(iface.GetMetadata())['arturl']).split('file://')[-1], 'rb').read()

def recv_thread(args):
    global active
    while active:
        message = args[0].receive()
        if args[0].socket is None: return "Finished"
        if message == "pause": iface.Pause()
        elif message == "play": iface.Play()
        elif message == "last": iface.Prev()
        elif message == "next": iface.Next()

@app.route('/api')
def api():
    session['last'] = None
    session['status'] = None
    if request.environ.get('wsgi.websocket'):
        ws = request.environ['wsgi.websocket']
        gevent.spawn(recv_thread, (ws, ))
        while active:
            gevent.sleep(1)
            if ws.socket is None: return "Finished"
            v = not bool(int(iface.GetStatus()[0]))
            # Lets get the percentage we're at
            meta = getMeta()
            perc = (float(iface.PositionGet())/float(meta['mtime']))*100
            ws.send(json.dumps({'tag': 'bar', 'value': perc}))

            #Do we need to update song info?
            if meta['title'] == session['last'] and session['status'] == v: continue
            else:
                session['last'] = meta['title']
                session['status'] = v
                t = str(float(meta['time'])/float(60)).split('.', 1)
                s = str(float('.'+t[1])*60).split('.')[0]
                meta['time'] = '%s:%s' % (t[0], s)
                ws.send(json.dumps({'tag': 'update', 'playing': v, 'meta': meta}))
    return "Bewbs :3"
if __name__ == "__main__":
    http_server = WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    http_server.serve_forever()
