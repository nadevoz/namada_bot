
import subprocess
import re
import json

RPC_NODE='http://127.0.0.1:26657'

# get current epoch number
def get_current_epoch():
    cmd = ['namadac', 'epoch', '--node', str(RPC_NODE)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout.strip()
    epoch = int(re.search(r'\d+', stdout).group(0))
    return epoch

# get a list of new proposals since the last query
def query_proposals(last_known: int):
    proposals = []

    # get latest on-chain prop id
    cmd = ['namadac', 'query-proposal', '--node', str(RPC_NODE)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    stdout = result.stdout.strip()
    id = int(re.search(r'id:\s+(\d+)', stdout).group(1))

    if id - last_known == 1: return proposals
    
    # iterate over all new proposals and query their detailed info
    for proposal_id in range(last_known, id):
        cmd = ['namadac', 'query-proposal', '--proposal-id', str(proposal_id), '--node', str(RPC_NODE)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if "No proposal found with id" in result.stdout:
            continue

        proposal_info = {}
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if ":" not in line:
                continue
            print(line)
            key, value = re.split(r':\s*', line, maxsplit=1)
            proposal_info[key.strip()] = value.strip()

        content = json.loads(proposal_info["Content"])
        proposal_info["Content"] = content

        proposals.append(proposal_info)
    return proposals

# format a single proposal data for TG notification
def format_notification(proposal: dict):
    content = proposal['Content']
    id = proposal['Proposal Id']
    start = proposal['Start Epoch']
    end = proposal['End Epoch']
    prop_type = proposal['Type']
    author = proposal['Author']
    abstract = content.get('abstract')
    authors = content.get('authors')
    details = content.get('details')
    discussion = content.get('discussions-to')
    license = content.get('license')
    motivation = content.get('motivation')
    title = content.get('title')
    text = f"Proposal #{id} is up for voting now!\nTitle:\n{title}\n\n"
    return text
    
