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
etc = session_bus.get_object('org.mpris.clementine', '/org/mpris/MediaPlayer2')
prop = dbus.Interface(etc, 'org.freedesktop.DBus.Properties')
iface = dbus.Interface(player, dbus_interface='org.freedesktop.MediaPlayer')

def getMeta(r):
    res = {}
    for k, v in dict(r).items():
        res[str(k)] = v
    return res

@app.route("/")
def routeIndex():
    return render_template('index.html')

@app.route('/getimage')
def routeGetImage():
    return open(str(dict(iface.GetMetadata())['arturl']).split('file://')[-1], 'rb').read()

def getTracks():
    res = {}
    for i in range(0, tracks.GetLength()):
        res[i] = getMeta(tracks.GetMetadata(i))
    return res

def getShuffle():
    return prop.Get('org.mpris.MediaPlayer2.Player', 'Shuffle')

def recv_thread(args):
    global active
    while active:
        message = args[0].receive()
        if args[0].socket is None: return "Finished"
        if message == "pause": iface.Pause()
        elif message == "play": iface.Play()
        elif message == "last": iface.Prev()
        elif message == "next": iface.Next()
        elif message == "vup": iface.VolumeUp(5)
        elif message == "vdown": iface.VolumeDown(5)
        elif message.startswith('ptrack'):
            tracks.PlayTrack(int(message.split('ptrack')[-1]))
        elif message.startswith('dtrack'):
            tracks.DelTrack(int(message.split('dtrack')[-1]))
        elif message == 'shuffon':
            prop.Set('org.mpris.MediaPlayer2.Player', 'Shuffle', True)
        elif message == "shuffoff":
            prop.Set('org.mpris.MediaPlayer2.Player', 'Shuffle', False)

@app.route('/api')
def api():
    session['last'] = None
    session['status'] = None
    session['tracks'] = 0
    session['track'] = -1
    session['vol'] = -1
    session['shuffle'] = None
    if request.environ.get('wsgi.websocket'):
        ws = request.environ['wsgi.websocket']
        gevent.spawn(recv_thread, (ws, ))
        while active:
            gevent.sleep(.5)
            if ws.socket is None: return "Finished"
            v = not bool(int(iface.GetStatus()[0]))

            # Lets get the percentage we're at
            meta = getMeta(iface.GetMetadata())
            perc = (float(iface.PositionGet())/float(meta['mtime']))*100
            tr = getTracks()
            ws.send(json.dumps({'tag': 'bar', 'value': perc}))

            #Do we need to update song info?
            if session['track'] != tracks.GetCurrentTrack() or session['vol'] != int(player.VolumeGet()) or session['shuffle'] != getShuffle():
                session['vol'] = int(player.VolumeGet())
                session['track'] = int(tracks.GetCurrentTrack())
                ws.send(json.dumps({'tag': 'state', 'vol': player.VolumeGet(), 'shuff': bool(getShuffle())}))
                ws.send(json.dumps({'tag': 'tracks', 'tracks': tr, 'cur': tracks.GetCurrentTrack()+1}))
            if session['tracks'] != len(tr) or meta['title'] != session['last'] or session['status'] != v:
                session['last'] = str(meta['title'])
                session['status'] = v
                session['tracks'] = len(tr)
                t = str(float(meta['time'])/float(60)).split('.', 1)
                s = str(float('.'+t[1])*60).split('.')[0]
                meta['time'] = '%s:%s' % (t[0], s)
                ws.send(json.dumps({'tag': 'update', 'playing': v, 'meta': meta}))
                ws.send(json.dumps({'tag': 'tracks', 'tracks': tr, 'cur': tracks.GetCurrentTrack()+1}))
            else: continue

    return "Bewbs :3"
if __name__ == "__main__":
    http_server = WSGIServer(('0.0.0.0', 5000), app, handler_class=WebSocketHandler)
    http_server.serve_forever()
