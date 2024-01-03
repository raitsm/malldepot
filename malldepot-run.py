# this is the run file for MallDepot app.
# start with:
# flask run - for production environment
# py malldepot-run.py - for development
import logging
from app import create_app              # , db


logging.basicConfig(level=logging.INFO, encoding='utf-8')

app = create_app()


if __name__ == "__main__":
    port = app.config.get("USE_PORT", 5000)
    if app.config["USE_HTTPS"]:
        print("Using HTTPS")
        app.run(ssl_context=("ssl_cert/malldepot-cert.pem", "ssl_key/malldepot-key.pem"), port=port, debug=True)
    else:
        print("Using HTTP")
        app.run(debug=True, port=port)    
else:
    print("Use py malldepot-run.py to launch the service.")
    
