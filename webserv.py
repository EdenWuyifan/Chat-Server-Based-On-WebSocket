from flask import Flask, request, send_from_directory

app = Flask(__name__, static_url_path='/static')
app.config['SERVER_NAME'] = 'localhost:8081'

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('client', path)


if __name__ == '__main__':
    app.run()
