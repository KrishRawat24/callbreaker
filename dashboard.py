from flask import Flask, render_template, jsonify
import json

app = Flask(__name__)

@app.route('/')
def index():
    with open('game_state.json') as f:
        data = json.load(f)
    return render_template('index.html', state=data)

@app.route('/api/state')
def state():
    with open('game_state.json') as f:
        data = json.load(f)
    return jsonify(data)

if __name__ == '__main__':
    app.run(port=5000)
