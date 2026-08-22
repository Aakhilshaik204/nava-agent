from abc import ABC, abstractmethod
from typing import List
import json
import os
from .schemas import Event, Receipt

class AuditLedger(ABC):
    """
    Append-only stream of chronological events.
    By design, this interface exposes NO methods for update or deletion.
    """
    
    @abstractmethod
    def append_event(self, event: Event) -> None:
        pass

    @abstractmethod
    def get_events(self, task_id: str) -> List[Event]:
        pass


class ImmutableReceiptStore(ABC):
    """
    Storage for structured, immutable records of completed actions.
    By design, this interface exposes NO methods for update or deletion.
    """
    
    @abstractmethod
    def store_receipt(self, receipt: Receipt) -> None:
        pass

    @abstractmethod
    def get_receipt(self, receipt_id: str) -> Receipt:
        pass


# ---------------------------------------------------------
# Basic Local JSONL Implementations (Append-Only Enforced)
# ---------------------------------------------------------

class JsonlAuditLedger(AuditLedger):
    def __init__(self, file_path: str):
        self.file_path = file_path
        # Ensure file exists
        if not os.path.exists(self.file_path):
            directory = os.path.dirname(self.file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            open(self.file_path, 'a').close()

    def append_event(self, event: Event) -> None:
        with open(self.file_path, 'a') as f:
            f.write(event.model_dump_json() + '\n')

    def get_events(self, task_id: str) -> List[Event]:
        events = []
        with open(self.file_path, 'r') as f:
            for line in f:
                event_data = json.loads(line)
                if event_data.get('task_id') == task_id:
                    events.append(Event(**event_data))
        return events

    get_events_by_task = get_events



class JsonlReceiptStore(ImmutableReceiptStore):
    def __init__(self, file_path: str):
        self.file_path = file_path
        if not os.path.exists(self.file_path):
            directory = os.path.dirname(self.file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            open(self.file_path, 'a').close()

    def store_receipt(self, receipt: Receipt) -> None:
        # Before appending, we optionally verify it doesn't already exist to prevent logical overwrites
        # (Though append-only nature means we just write to the end)
        with open(self.file_path, 'a') as f:
            f.write(receipt.model_dump_json() + '\n')

    def get_receipt(self, receipt_id: str) -> Receipt:
        with open(self.file_path, 'r') as f:
            for line in f:
                receipt_data = json.loads(line)
                if receipt_data.get('receipt_id') == receipt_id:
                    return Receipt(**receipt_data)
        raise KeyError(f"Receipt {receipt_id} not found")

class LocalFileReceiptStore(ImmutableReceiptStore):
    """
    Stores all receipts from a single task in a unified JSON file in a specified directory,
    making it extremely easy to read the entire execution trace of a query.
    """
    def __init__(self, directory: str = "receipts"):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def store_receipt(self, receipt: Receipt) -> None:
        file_path = os.path.join(self.directory, f"{receipt.task_id}.json")
        receipts_list = []
        
        # Read existing list if the file already exists
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    receipts_list = json.load(f)
                except json.JSONDecodeError:
                    pass
                    
        # Append new receipt and save
        receipts_list.append(json.loads(receipt.model_dump_json()))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(receipts_list, f, indent=4)

    def get_receipt(self, receipt_id: str) -> Receipt:
        # Note: Since receipts are grouped by task_id, retrieving by exact receipt_id 
        # requires scanning files. In a real DB this is an indexed query. 
        # For local files, we'll just scan.
        for filename in os.listdir(self.directory):
            if filename.endswith(".json"):
                with open(os.path.join(self.directory, filename), 'r', encoding='utf-8') as f:
                    try:
                        receipts_list = json.load(f)
                        for r_data in receipts_list:
                            if r_data.get('receipt_id') == receipt_id:
                                return Receipt(**r_data)
                    except json.JSONDecodeError:
                        pass
        raise KeyError(f"Receipt {receipt_id} not found")

    def get_receipts_by_agent(self, agent_id: str) -> List[Receipt]:
        matched = []
        for filename in os.listdir(self.directory):
            if filename.endswith(".json"):
                with open(os.path.join(self.directory, filename), 'r', encoding='utf-8') as f:
                    try:
                        receipts_list = json.load(f)
                        for r_data in receipts_list:
                            if r_data.get('agent_id') == agent_id:
                                matched.append(Receipt(**r_data))
                    except json.JSONDecodeError:
                        pass
        return matched
