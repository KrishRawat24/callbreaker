from flask import Flask, render_template
import json

app = Flask(__name__)

@app.route('/')
def index():
    try:
        with open('game_state.json') as f:
            state = json.load(f)
    except:
        state = {}
    return render_template("index.html", state=state)

if __name__ == '__main__':
    app.run(port=8080)
