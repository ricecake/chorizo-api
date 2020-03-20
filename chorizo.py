from api_tools import JsonApi
import classes
import time
app = JsonApi(__name__)

with app.subroute('/test') as test_api:
    @test_api.route('/')
    def hello():
        name = request.args.get("name", "World")
        return f'Hello, {escape(name)}!'

    @test_api.route('/ping',
        methods=['GET', 'POST'],
        restricted=False,
        validation={ "test": {"type": "string" }}
    )
    def util_ping():
        return "pong"

    @app.route('/make',
        methods=['POST'],
        restricted=False,
    )
    def test_ping(**kwargs):
        return classes.Identity.create(identity="fooze: {}".format(time.time()))

app.run("localhost", 8089)
