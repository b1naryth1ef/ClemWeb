from flask import Flask, render_template, request
from geventwebsocket.handler import WebSocketHandler
from gevent.pywsgi import WSGIServer
import dbus, json, time, thread

app = Flask(__name__)
active = True
app.debug = True
session_bus = dbus.SessionBus()
player = session_bus.get_object('org.mpris.clementine', '/Player')
iface = dbus.Interface(player, dbus_interface='org.freedesktop.MediaPlayer')

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

@app.route('/api')
def api():
    if request.environ.get('wsgi.websocket'):
        ws = request.environ['wsgi.websocket']
        while active:
            v = not bool(int(iface.GetStatus()[0]))
            ws.send(json.dumps({'tag': 'update', 'playing': v, 'meta': getMeta()}))
            message = ws.receive()
            if message == "pause": iface.Pause()
            elif message == "play": iface.Play()
            elif message == "last": iface.Prev()
            elif message == "next": iface.Next()
            time.sleep(1)

if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), app, handler_class=WebSocketHandler)
    http_server.serve_forever()
