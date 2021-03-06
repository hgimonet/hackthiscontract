import json
import os

from flask import Flask, render_template, request, redirect, g, url_for, Response

import config as constants
import easyweb3
import util

app = Flask(__name__)
deployers = {}
graders = {}


@app.before_first_request
def init_application():
    util.init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route("/")
def hello():
    return render_template('index.html')


@app.route("/dashboard/<string:address>")
@util.check_address_decorator
def dashboard(address):
    challenges = {}
    for challenge_id in constants.CHALLENGES:
        challenges[challenge_id] = json.loads(open("challenges/" + challenge_id + ".json").read().strip())
        challenges[challenge_id]["code"] = open("challenges/" + challenge_id + ".sol").read().strip()
        challenge_id_int = int(challenge_id.split("_")[0])
        challenges[challenge_id]["status"] = util.get_status(address, challenge_id_int)
        challenges[challenge_id]["deployed"] = (len(challenges[challenge_id]["status"]) == 3)
    return render_template('dashboard.html', address=address, challenge_ids=constants.CHALLENGES, challenges=challenges,
                           exists=util.exists(address))


@util.check_address_decorator
def get_deploy_thread_status(address, contract):
    global deployers
    deploy_key = (address, contract)
    if not deploy_key in deployers:
        web3_instance = easyweb3.EasyWeb3()
        deployers[deploy_key] = web3_instance
        web3_instance.deploy_named_solidity_contract(contract, address)
    else:
        web3_instance = deployers[deploy_key]
    return web3_instance.deploy_status()

@util.check_address_decorator
def get_grade_thread_status(address, contract_name):
    global graders
    grade_key = (address, contract_name)
    if not grade_key in graders:
        web3_instance = easyweb3.EasyWeb3()
        graders[grade_key] = web3_instance
        contract_addr = util.get_deployed_contract_address_for_challenge(address, util.get_contract_number(contract_name))
        web3_instance.grade_challenge(contract_name, address, contract_addr)
    else:
        web3_instance = graders[grade_key]
    return web3_instance.deploy_status()

@app.route("/done/<string:address>/<string:contract>")
@util.check_address_decorator
def done(address, contract):
    print("deploying:\t{} {}".format(address, contract))
    status = get_deploy_thread_status(address, contract)

    if status[1] is not None and status[0] == "deployed":
        print("Status is not none: " + str(status))
        global deployers
        deploy_key = (address, contract)
        del deployers[deploy_key] # TODO race condition?
        util.write_address(address, util.get_contract_number(contract), status[1])
    if status[0]:
        return status[0]
    else:
        return "Starting deployment process"


@app.route("/deploy/<string:address>/<string:contract>", methods=['POST'])
@util.check_address_decorator
def deploy(address, contract):
    status = util.get_status(address, util.get_contract_number(contract))
    if "not started" in status[0].lower():
        return render_template('deploy.html', deployed=False, address=address, contract=contract)
    else:
        return redirect(url_for('view', _external=True, _scheme='https', address=address, contract=contract))


@app.route("/view/<string:address>/<string:contract>")
@util.check_address_decorator
def view(address, contract):
    status = util.get_status(address, util.get_contract_number(contract))
    if "not started" in status[0].lower():
        return "Not started!"
    contract_code = open("challenges/" + contract + ".sol").read().strip()
    contract_desc = json.loads(open("challenges/" + contract + ".json").read().strip())["description"]
    return render_template('view.html', deployed=True, done=("done" in status[0].lower()), status=status,
                           address=address, contract=contract, contract_code=contract_code,
                           contract_desc=contract_desc)

@app.route("/grade/<string:address>/<string:contract_name>")
@util.check_address_decorator
def grade(address, contract_name):
    print("grading:\t{} {}".format(address, contract_name))
    status = get_grade_thread_status(address, contract_name)

    if status[1] is not None and status[0] == "graded":
        print("graded complete: " + str(status))
        global graders
        grade_key = (address, contract_name)
        del graders[grade_key]
    if status[0]:
        return status[0]
    else:
        return "Starting grading process"


@app.route("/update/<string:address>/<string:contract_name>")
@util.check_address_decorator
def update(address, contract_name):
    file_name = "challenges/" + contract_name + ".py"
    if not os.path.exists(file_name) or not os.path.isfile(file_name):
        print("Challenge validator not found for contract: " + contract_name)
        return redirect(url_for('view', _external=True, _scheme='https', address=address, contract=contract))

    status_blob = util.get_status(address, util.get_contract_number(contract_name))
    contract_addr = status_blob[2].strip()
    status = status_blob[0].lower()
    if "unfinished" in status:
        return render_template('grade.html', address=address, contract_name=contract_name)
    else:
        return redirect(url_for('dashboard', _external=True, _scheme='https', address=address))


@app.route("/redeploy/<string:address>/<string:contract_name>", methods=['POST'])
@util.check_address_decorator
def redeploy(address, contract_name):
    print("Redeploying {}, {}".format(address, contract_name))
    util.erase_challenge_deployed_address_from_db(address, util.get_contract_number(contract_name))
    return redirect(url_for('deploy', _external=True, _scheme='https', _method="POST", address=address, contract=contract_name), code=307)


@app.route("/ranking")
def ranking():
    return render_template("ranking.html", users=util.get_ranking_from_db())


if __name__ == "__main__":
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    app.run(host=constants.SERVER_HOST, port=constants.SERVER_PORT)
