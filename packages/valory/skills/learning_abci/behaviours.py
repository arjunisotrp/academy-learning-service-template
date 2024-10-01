# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains round behaviours of LearningAbciApp."""
import requests
from abc import ABC
from typing import Generator, List, Set, Type, cast, Dict

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.learning_abci.models import Params, SharedState
from packages.valory.skills.learning_abci.payloads import (
    APICheckPayload,
    IPFSSendPayload,
    IPFSGetPayload,
    DecisionMakingPayload,
    TxPreparationPayload,
    MultiSendTxPayload
)
from packages.valory.skills.learning_abci.rounds import (
    APICheckRound,
    IPFSSendRound,
    IPFSGetRound,
    DecisionMakingRound,
    Event,
    LearningAbciApp,
    SynchronizedData,
    TxPreparationRound,
    MultiSendTxRound,
)
from packages.valory.contracts.multisend.contract import (
    MultiSendContract,
    MultiSendOperation,
)
from packages.valory.protocols.contract_api import ContractApiMessage
from hexbytes import HexBytes
from packages.valory.contracts.erc20.contract import ERC20
from packages.valory.contracts.gnosis_safe.contract import (
    GnosisSafeContract,
    SafeOperation,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (
    hash_payload_to_hex,
)
from packages.valory.skills.transaction_settlement_abci.payload_tools import (hash_payload_to_hex,)
from tempfile import mkdtemp
import multibase
import multicodec
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from dataclasses import asdict, dataclass
from pathlib import Path

VAL_ETHER = 10**18
VAL = 1
HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
TX_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
METADATA_FILENAME = "large.json"


class LearningBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the learning_abci skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)
    
    @property
    def metadata_filepath(self) -> str:
        """Get the filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)


class APICheckBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """APICheckBehaviour"""

    matching_round: Type[AbstractRound] = APICheckRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            price = yield from self.get_price()
            balance = yield from self.get_balance()
            payload = APICheckPayload(sender=sender, price=price, balance=balance)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_price(self):
        """Get token price from Coingecko"""
        # Interact with Coingecko's API
        # result = yield from self.get_http_response("coingecko.com")
        yield
        price = 1.0
        self.context.logger.info(f"Price is {price}")
        return price

    def get_balance(self):
        """Get balance"""
        # Use the contract api to interact with the ERC20 contract
        result = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,
            contract_address=self.params.contract_token_address,
            contract_id=str(ERC20.contract_id),
            contract_callable="check_balance",
            account=self.synchronized_data.safe_contract_address,
            chain_id=GNOSIS_CHAIN_ID,)
        
        if result.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(f"{result}..error in getting balance")
            return False
        wallet_balance = (result.raw_transaction.body.get("wallet",None))/10**18
        token_balance = (result.raw_transaction.body.get("token",None))/10**18

        self.context.logger.info(f"wallet_balance : {wallet_balance}")
        balance = token_balance
        self.context.logger.info(f"token balance is {balance}")
        return balance

class IPFSSendBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """IPFS Send Behaviour"""
    matching_round: Type[AbstractRound] = IPFSSendRound
    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            metadata_hash = yield from self._send_large_metadata_to_ipfs()
            payload = IPFSSendPayload(sender=sender,metadata_hash=metadata_hash)
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        self.set_done()
        
    def _send_large_metadata_to_ipfs(self):
        """Send large metadata to IPFS."""
        @dataclass
        class MetadataItems:
            id: str
            message: str
            signature: str
            blockNumber: str
            version: str
        
        @dataclass
        class MetaData:
            updateds: List[MetadataItems]
        @dataclass
        class Data:
            data: MetaData   

        metadata_subgraph = self.get_subgraph()
        metadataItems = Data(**metadata_subgraph)
        metadata_hash = yield from self.send_to_ipfs(
            self.metadata_filepath, asdict(metadataItems), filetype=SupportedFiletype.JSON
        )
        self.context.logger.info(f"metadata uploaded, metadata hash: {metadata_hash}")
        if metadata_hash is None:
            return False

        return metadata_hash
    
    def get_subgraph(self):
        """Get a subgraph"""

        content = {"query": "{ updateds(first: 10) { id message signature blockNumber } }", "operationName": "Subgraphs", "variables": {}}
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        url=self.params.subgraph_api_endpoint
        res = requests.post(url, json=content, headers=headers) 
        if res.status_code != 200:
            raise ConnectionError(
                "Something went wrong while trying to communicate with the subgraph "
                f"(Error: {res.status_code})!\n{res.text}"
            )
        body = res.json()
        if "errors" in body.keys():
            raise ValueError(f"The given query is not correct")
        return body
    
class IPFSGetBehaviour(LearningBaseBehaviour):  # pylint: disable=too-many-ancestors
    """IPFS Get Behaviour"""
    matching_round: Type[AbstractRound] = IPFSGetRound
    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            metadata = yield from self._get_large_metadata_from_ipfs()
            self.context.logger.info(f"received metadata : {metadata}")
            payload = IPFSGetPayload(sender=sender)
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        self.set_done()

    def _get_large_metadata_from_ipfs(self):
        """Get large metadata to IPFS."""   
        metadata_data = yield from self.get_from_ipfs(  # type: ignore
            self.synchronized_data.metadata_hash,
            filetype=SupportedFiletype.JSON,
        ) 
        return metadata_data

class DecisionMakingBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            event = self.get_event()
            payload = DecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_event(self):
        """Get the next event"""
        # Using the token Balance from the previous round, decide whether we should make a Single tx or multi send tx
        self.context.logger.info(f"{SynchronizedData.tx_submitter} round sent the last transaction!")
        if self.synchronized_data.balance < 5:
            event = Event.TRANSACT.value
            self.context.logger.info(f"Event is {event}.. Do single tx")
        else:
            event = Event.MULTI_TRANSACT.value
            self.context.logger.info(f"Event is {event}.. Do multi send tx")
        return event


class TxPreparationBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """TxPreparationBehaviour"""

    matching_round: Type[AbstractRound] = TxPreparationRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        self.context.logger.info(f"Tx Preparation..")
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address
            tx_hash = yield from self.get_tx_hash()

            # params here need to match those in _get_safe_tx_hash()
            payload_data = hash_payload_to_hex(
            safe_tx_hash=tx_hash,
            ether_value=VAL_ETHER, 
            safe_tx_gas=SAFE_GAS,
            to_address=self.params.transfer_target_address,
            data=TX_DATA,
            )

            payload = TxPreparationPayload(
                sender=sender, tx_submitter="TxPreparationRound", tx_hash=payload_data
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_tx_hash(self):
        """Get the tx hash"""
        # We need to prepare a 1 wei transfer from the safe to another (configurable) account.
        result = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_STATE,
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address= self.params.transfer_target_address,
            value=VAL_ETHER,
            data=TX_DATA,
            safe_tx_gas=SAFE_GAS,
            chain_id=GNOSIS_CHAIN_ID
        )

        self.context.logger.info(f"result is : {result}")

        if result.performative != ContractApiMessage.Performative.STATE:
            self.context.logger.error(f"{result}..error in getting hash")
            return False
        
        tx_hash = cast(str, result.state.body["tx_hash"])[2:]

        self.context.logger.info(f"Transaction hash is {tx_hash}")
        return tx_hash

class MultiSendTxBehaviour(
    LearningBaseBehaviour
):  # pylint: disable=too-many-ancestors
    """MultiSendTxBehaviour"""
    matching_round: Type[AbstractRound] = MultiSendTxRound
    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            multisend_txs = []
            tx_1 = yield from self.transfer_tx()
            multisend_txs.append(tx_1)

            tx_2 = yield from self.token_transfer_tx()
            multisend_txs.append(tx_2)

            contract_api_msg = yield from self.get_contract_api_response(
                performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
                contract_address=self.params.multisend_contract_address,
                contract_id=str(MultiSendContract.contract_id),
                contract_callable="get_tx_data",
                multi_send_txs=multisend_txs,
                chain_id=GNOSIS_CHAIN_ID
            )
            multisend_data = cast(str, contract_api_msg.raw_transaction.body["data"])
            multisend_data = multisend_data[2:]
            self.context.logger.info(f"multisend data: {multisend_data}")

            contract_api_msg = yield from self.get_contract_api_response(
                performative=ContractApiMessage.Performative.GET_STATE,  # type: ignore
                contract_address=self.synchronized_data.safe_contract_address,
                contract_id=str(GnosisSafeContract.contract_id),
                contract_callable="get_raw_safe_transaction_hash",
                to_address=self.params.transfer_target_address,
                value=sum(tx["value"] for tx in multisend_txs),
                data=bytes.fromhex(multisend_data),
                operation=SafeOperation.DELEGATE_CALL.value,
                safe_tx_gas=SAFE_GAS,
                chain_id=GNOSIS_CHAIN_ID,
            )
            self.context.logger.info(f"safe tx hash msg: {contract_api_msg}")
            if contract_api_msg.performative != ContractApiMessage.Performative.STATE:
                self.context.logger.error(
                    f"Could not get Multisend Gnosis Safe tx hash. "
                    f"Expected: {ContractApiMessage.Performative.STATE.value}, "
                    f"Actual: {contract_api_msg.performative.value}"
                )
                return None
            
            safe_tx_hash = cast(str, contract_api_msg.state.body["tx_hash"])
            safe_tx_hash = safe_tx_hash[2:]
            self.context.logger.info(f"Safe tx hash: {safe_tx_hash}")

            tx_hash_payload = hash_payload_to_hex(
                safe_tx_hash=safe_tx_hash,
                ether_value=sum(tx["value"] for tx in multisend_txs),
                safe_tx_gas=SAFE_GAS,
                to_address=self.params.transfer_target_address,
                data=bytes.fromhex(multisend_data),
                operation=SafeOperation.DELEGATE_CALL.value,
            )

            self.context.logger.info(f"tx hash: {tx_hash_payload}")
            payload = MultiSendTxPayload(
                sender=sender,tx_submitter="MultiSendTxRound", tx_hash=tx_hash_payload
            )
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()
        self.set_done()
    
    def transfer_tx(self):
        """Get the tx data"""

        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.synchronized_data.safe_contract_address,
            contract_id=str(GnosisSafeContract.contract_id),
            contract_callable="get_raw_safe_transaction_hash",
            to_address=self.params.transfer_target_address,
            value=VAL,
            data=TX_DATA,
            safe_tx_gas=SAFE_GAS,
            chain_id=GNOSIS_CHAIN_ID,
        )
   
        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Could not get transfer hash. "
                f"Expected: {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "
                f"Actual: {response_msg.performative.value}"
            )
            return None
        self.context.logger.info(f"response msg: {response_msg}")
        tx_hash_data = cast(str, response_msg.raw_transaction.body["tx_hash"])

        return {
            "operation": MultiSendOperation.CALL,
            "to":self.params.transfer_target_address,
            "value": VAL,
            "data": tx_hash_data,
        }
    
    def token_transfer_tx(self):
        """Get the tx data"""
        self.context.logger.info(f"Token transfer")
        response_msg = yield from self.get_contract_api_response(
            performative=ContractApiMessage.Performative.GET_RAW_TRANSACTION,  # type: ignore
            contract_address=self.params.contract_token_address,
            contract_id=str(ERC20.contract_id),
            contract_callable="build_transfer_tx",
            receiver=self.params.transfer_target_address, 
            amount=VAL,
        )

        if response_msg.performative != ContractApiMessage.Performative.RAW_TRANSACTION:
            self.context.logger.error(
                f"Could not get token transfer hash. "
                f"Expected: {ContractApiMessage.Performative.RAW_TRANSACTION.value}, "
                f"Actual: {response_msg.performative.value}"
            )
            return None
        tx_hash_data = HexBytes(
            cast(bytes, response_msg.raw_transaction.body["data"]).hex()
        )
        return {
            "operation": MultiSendOperation.CALL,
            "to": self.params.contract_token_address,
            "value": VAL,
            "data": tx_hash_data,
            "chain_id":GNOSIS_CHAIN_ID
        }

class LearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = APICheckBehaviour
    abci_app_cls = LearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore
        APICheckBehaviour,
        IPFSSendBehaviour,
        IPFSGetBehaviour,
        DecisionMakingBehaviour,
        TxPreparationBehaviour,
        MultiSendTxBehaviour,
    ]
