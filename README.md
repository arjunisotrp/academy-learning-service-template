## Learning Extended Service

APICheckBehaviour:
- Get ERC20 token balance by interacting with the ERC20 smart contract

IPFSSendBehaviour:
- This task collects Subgraph json data by querying the subgraph on the decentralized network and 
- send the json data to IPFS using send_to_ipfs interface.
- Received metadata file hash is stored on synchronized data.

IPFSGetBehaviour:
- This behaviour uses metadata file hash stored in synchronized data and prints the metadata.
	
DecisionMakingBehaviour:
- This use the balance from APICheck round and decides on making single transaction or multiple transaction based on some pre-defined value. 

TxPreparationBehaviour:
- Make single safe transaction. From safe wallet to another agent address of the 4 agents available.
- Convert the safe tx hash to format that is supported by transaction settlement abci and submit it.

MultiSendTxBehaviour:
- Make multiple safe transactions.
	- 1. From safe to another agent address of the 4 agents available with the native xDAI tokens
	- 2. From safe to another agent address of the 4 agents available with the custom ERC20 tokens 
- Append multiple txs as one and send to Multisend contract.
- Convert the safe tx hash to format that is supported by transaction settlement abci and submit it.

## System requirements

- Python `>=3.10`
- [Tendermint](https://docs.tendermint.com/v0.34/introduction/install.html) `==0.34.19`
- [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `==0.6.0`
- [Pip](https://pip.pypa.io/en/stable/installation/)
- [Poetry](https://python-poetry.org/)
- [Docker Engine](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- [Set Docker permissions so you can run containers as non-root user](https://docs.docker.com/engine/install/linux-postinstall/)


## Run you own agent

### Get the code

1. Clone this repo:

    ```
    git clone https://github.com/arjunisotrp/academy-learning-service-template.git
    ```

2. Create the virtual environment:

    ```
    cd academy-learning-service
    poetry shell
    poetry install
    ```

3. Sync packages:

    ```
    autonomy packages sync --update-packages
    ```

### Prepare the data

1. Prepare a `keys.json` file containing wallet address and the private key for each of the four agents.

    ```
    autonomy generate-key ethereum -n 4
    ```

2. Prepare a `ethereum_private_key.txt` file containing one of the private keys from `keys.json`. Ensure that there is no newline at the end.

3. Deploy a [Safe on Gnosis](https://app.safe.global/welcome) (it's free) and set your agent addresses as signers. Set the signature threshold to 3 out of 4.

4. Create a [Tenderly](https://tenderly.co/) account and from your dashboard create a fork of Gnosis chain (virtual testnet).

5. From Tenderly, fund your agents and Safe with a small amount of xDAI, i.e. $0.02 each.

6. Make a copy of the env file:

    ```
    cp sample.env .env
    ```

7. Fill in the required environment variables in .env. These variables are: `ALL_PARTICIPANTS`, `GNOSIS_LEDGER_RPC`, `CONTRACT_TOKEN_ADDRESS`, `TRANSFER_TARGET_ADDRESS`, `MULTISEND_CONTRACT_ADDRESS`, `SUBGRAPH_API_ENDPOINT`,  and `SAFE_CONTRACT_ADDRESS`. You will need to get a API Key, subgraph id from [Subgraph](https://thegraph.com/explorer/subgraphs) and update SUBGRAPH_API_ENDPOINT(https://gateway.thegraph.com/api/{api_key}/subgraphs/id/{subgraph_id}). Set `GNOSIS_LEDGER_RPC` to your Tenderly fork Admin RPC.

### Run a single agent

1. Verify that `ALL_PARTICIPANTS` in `.env` contains only 1 address.

2. Run the agent:

    ```
    bash run_agent.sh
    ```

### Run the service (4 agents)

1. Check that Docker is running:

    ```
    docker
    ```

2. Verify that `ALL_PARTICIPANTS` in `.env` contains 4 addresses.

3. Run the service:

    ```
    bash run_service.sh
    ```

4. Look at the service logs for one of the agents (on another terminal):

    ```
    docker logs -f learningservice_abci_0
    ```


