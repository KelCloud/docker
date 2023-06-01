import docker
from flask import Flask, render_template, request

app = Flask(__name__)
client = docker.from_env()

@app.route('/')
def index():
    return render_template("index.html", nama='rhazes')


@app.route('/create_container', methods=["GET", "POST"])
def create_container():
    if request.method == 'POST':
        name = request.form['name']
        image = request.form['image']
        container = client.containers.run(image, detach=True)
        return container.id
        
    return render_template("create_container.html")


app.run(host='0.0.0.0', port=1025, debug=True)
 