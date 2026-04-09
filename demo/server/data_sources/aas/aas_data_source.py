import base64
import logging
import threading
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable

import httpx

from ..data_interface import I3XDataSource
from .aas_data import AAS_DATA, AAS_NAMESPACE_URI, VIRTUAL_INSTANCES


class AASDataSource(I3XDataSource):
    """AAS (Asset Administration Shell) data source implementation.

    Connects to a TwinSphere (or AAS-compatible) viewer API and projects
    AAS Shells and Submodels into the i3X address space.

    Mapping:
        Shell   -> root i3X instance  (type: aas-shell-type)
        Submodel -> child i3X instance (type: aas-submodel-type), linked via HasComponent

    Element ID scheme:
        Shells:    "aas:<base64(aasId)>"
        Submodels: "aas:<base64(aasId)>:<base64(submodelId)>"
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_url = config.get("base_url", "").rstrip("/")
        self.logger = logging.getLogger(__name__)
        self.update_callback = None

        # Caches populated on start()
        self._shells: List[Dict[str, Any]] = []           # raw shell payloads
        self._instances: List[Dict[str, Any]] = []         # i3X instance dicts
        self._instance_index: Dict[str, Dict[str, Any]] = {}  # elementId -> instance
        self._submodel_values: Dict[str, Any] = {}         # elementId -> fetched submodel content
        self._lock = threading.Lock()
        self._client: Optional[httpx.Client] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, update_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        self.update_callback = update_callback
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0)
        self._load_shells()

    def stop(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Internal: fetch & cache
    # ------------------------------------------------------------------

    @staticmethod
    def _b64(value: str) -> str:
        """Base64-encode a string for use in API paths."""
        return base64.b64encode(value.encode("utf-8")).decode("ascii")

    @staticmethod
    def _element_id_for_shell(aas_id: str) -> str:
        return f"aas:{AASDataSource._b64(aas_id)}"

    @staticmethod
    def _element_id_for_submodel(aas_id: str, submodel_id: str) -> str:
        return f"aas:{AASDataSource._b64(aas_id)}:{AASDataSource._b64(submodel_id)}"

    def _parse_element_id(self, element_id: str) -> Dict[str, Optional[str]]:
        """Decode an element ID back to its AAS components.

        Returns dict with 'aasId' (always present) and 'submodelId' (if submodel).
        """
        parts = element_id.split(":")
        if len(parts) < 2 or parts[0] != "aas":
            return {}
        aas_id = base64.b64decode(parts[1]).decode("utf-8")
        submodel_id = base64.b64decode(parts[2]).decode("utf-8") if len(parts) >= 3 else None
        return {"aasId": aas_id, "submodelId": submodel_id}

    def _load_shells(self) -> None:
        """Fetch all shells from the AAS API (handling cursor pagination) and build instance cache."""
        all_shells = []
        cursor = None

        while True:
            params = {}
            if cursor:
                params["cursor"] = cursor

            try:
                resp = self._client.get("/api/ShellList", params=params)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as e:
                self.logger.error(f"Failed to fetch shell list: {e}")
                break

            # The response may be a paginated wrapper or a plain list.
            if isinstance(payload, dict):
                result = payload.get("result", payload.get("assetAdministrationShells", []))
                if isinstance(result, list):
                    all_shells.extend(result)
                # Cursor-based pagination
                paging = payload.get("paging_metadata", payload.get("pagingMetadata", {}))
                cursor = paging.get("cursor") if isinstance(paging, dict) else None
            elif isinstance(payload, list):
                all_shells.extend(payload)
                cursor = None
            else:
                break

            if not cursor:
                break

        self.logger.info(f"Loaded {len(all_shells)} AAS shells from {self.base_url}")
        self._shells = all_shells
        self._build_instance_cache()

    def _build_instance_cache(self) -> None:
        """Convert raw shells into i3X instances, fetch submodel references,
        and merge in virtual instances (folders, EVs, etc.)."""
        instances = []
        index = {}
        shell_eids = []  # track all shell element IDs for the Digital Passports folder

        for shell in self._shells:
            aas_id = shell.get("id", shell.get("identification", ""))
            display_name = shell.get("idShort", aas_id)
            description = ""
            desc_field = shell.get("description")
            if isinstance(desc_field, list) and desc_field:
                # AAS descriptions are lang-string arrays
                description = desc_field[0].get("text", "")
            elif isinstance(desc_field, str):
                description = desc_field

            shell_eid = self._element_id_for_shell(aas_id)
            shell_eids.append(shell_eid)
            submodel_eids = []

            # Fetch submodel references for this shell
            b64_aas_id = self._b64(aas_id)
            try:
                resp = self._client.get(f"/api/submodels/{b64_aas_id}")
                resp.raise_for_status()
                submodel_refs = resp.json()
                if not isinstance(submodel_refs, list):
                    submodel_refs = []
            except Exception as e:
                self.logger.warning(f"Failed to fetch submodels for shell {aas_id}: {e}")
                submodel_refs = []

            for sm_ref in submodel_refs:
                # Each submodel reference has keys[] with type/value
                sm_keys = sm_ref.get("keys", [])
                sm_id = None
                for key in sm_keys:
                    if key.get("type") == "Submodel":
                        sm_id = key.get("value")
                        break
                if not sm_id and sm_keys:
                    sm_id = sm_keys[0].get("value")
                if not sm_id:
                    continue

                sm_eid = self._element_id_for_submodel(aas_id, sm_id)
                submodel_eids.append(sm_eid)

                sm_semantic_id = sm_ref.get("referredSemanticId", "")
                # Derive a display name from the submodel ID (last segment or idShort)
                sm_display = sm_id.rsplit("/", 1)[-1] if "/" in sm_id else sm_id

                sm_instance = {
                    "elementId": sm_eid,
                    "displayName": sm_display,
                    "description": f"Submodel: {sm_id}",
                    "typeElementId": "aas-submodel-type",
                    "parentId": shell_eid,
                    "isComposition": False,
                    "relationships": {
                        "ComponentOf": shell_eid,
                    },
                    # Stash raw IDs for later value fetching
                    "_aasId": aas_id,
                    "_submodelId": sm_id,
                    "_semanticId": sm_semantic_id,
                }
                instances.append(sm_instance)
                index[sm_eid] = sm_instance

            # Shells are children of the "Digital Passports" folder
            shell_instance = {
                "elementId": shell_eid,
                "displayName": display_name,
                "description": description,
                "typeElementId": "aas-shell-type",
                "parentId": "digital-passports",
                "isComposition": True if submodel_eids else False,
                "relationships": {
                    "HasParent": "digital-passports",
                },
                # Stash raw shell payload for value responses
                "_raw": shell,
                "_aasId": aas_id,
            }
            if submodel_eids:
                shell_instance["relationships"]["HasComponent"] = submodel_eids

            instances.append(shell_instance)
            index[shell_eid] = shell_instance

        # Merge in virtual instances (deep-copy to avoid mutating the static data)
        import copy
        for vi in VIRTUAL_INSTANCES:
            inst = copy.deepcopy(vi)

            # Wire up the "Digital Passports" folder's HasChildren with actual shell IDs
            if inst["elementId"] == "digital-passports":
                inst["relationships"]["HasChildren"] = shell_eids

            # Resolve _linkedAasId into bidirectional graph relationships
            linked_aas_id = inst.pop("_linkedAasId", None)
            if linked_aas_id:
                shell_eid = self._element_id_for_shell(linked_aas_id)
                inst["relationships"]["HasDigitalPassport"] = shell_eid

                # Add the reverse relationship on the shell instance
                if shell_eid in index:
                    shell_inst = index[shell_eid]
                    shell_inst["relationships"]["DigitalPassportOf"] = inst["elementId"]

            instances.append(inst)
            index[inst["elementId"]] = inst

        with self._lock:
            self._instances = instances
            self._instance_index = index

    def _fetch_submodel_value(self, aas_id: str, submodel_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full submodel content from the AAS API."""
        eid = self._element_id_for_submodel(aas_id, submodel_id)

        # Check cache first
        with self._lock:
            if eid in self._submodel_values:
                return self._submodel_values[eid]

        b64_aas_id = self._b64(aas_id)
        b64_sm_id = self._b64(submodel_id)
        try:
            resp = self._client.get(f"/api/submodels/{b64_aas_id}/submodel/{b64_sm_id}")
            resp.raise_for_status()
            value = resp.json()
        except Exception as e:
            self.logger.warning(f"Failed to fetch submodel {submodel_id} for shell {aas_id}: {e}")
            return None

        with self._lock:
            self._submodel_values[eid] = value
        return value

    # ------------------------------------------------------------------
    # I3XDataSource interface: exploratory
    # ------------------------------------------------------------------

    def get_namespaces(self) -> List[Dict[str, Any]]:
        return AAS_DATA["namespaces"]

    def get_object_types(self, namespace_uri: Optional[str] = None) -> List[Dict[str, Any]]:
        types = AAS_DATA["objectTypes"]
        if namespace_uri:
            types = [t for t in types if t["namespaceUri"] == namespace_uri]
        return types

    def get_object_type_by_id(self, element_id: str) -> Optional[Dict[str, Any]]:
        for t in AAS_DATA["objectTypes"]:
            if t["elementId"] == element_id:
                return t
        return None

    def get_relationship_types(self, namespace_uri: Optional[str] = None) -> List[Dict[str, Any]]:
        types = AAS_DATA["relationshipTypes"]
        if namespace_uri:
            types = [t for t in types if t["namespaceUri"] == namespace_uri]
        return types

    def get_relationship_type_by_id(self, element_id: str) -> Optional[Dict[str, Any]]:
        for rt in AAS_DATA["relationshipTypes"]:
            if rt["elementId"] == element_id:
                return rt
        return None

    def get_instances(self, type_id: Optional[str] = None, root: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            results = list(self._instances)

        if type_id:
            results = [i for i in results if i["typeElementId"] == type_id]
        if root:
            results = [i for i in results if i.get("parentId") is None]

        return [self._strip_internal(i) for i in results]

    def get_instance_by_id(self, element_id: str, values: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock:
            instance = self._instance_index.get(element_id)
        if not instance:
            return None
        return instance if values else self._strip_internal(instance)

    def get_all_instances(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [self._strip_internal(i) for i in self._instances]

    # ------------------------------------------------------------------
    # I3XDataSource interface: values
    # ------------------------------------------------------------------

    def get_instance_values_by_id(
        self,
        element_id: str,
        startTime: Optional[str] = None,
        endTime: Optional[str] = None,
        maxDepth: int = 1,
        returnHistory: bool = False,
    ) -> Optional[Dict[str, Any]]:
        return self._get_values_recursive(element_id, startTime, endTime, returnHistory, maxDepth)

    def _get_values_recursive(self, element_id, startTime, endTime, returnHistory, max_depth):
        instance = self.get_instance_by_id(element_id, values=True)
        if not instance:
            return None

        inner_result = {}
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Build VQT for this element
        value = self._get_raw_value(instance)
        if value is not None:
            vqt = {"value": value, "quality": "Good", "timestamp": now}
            inner_result["data"] = [vqt]
        else:
            inner_result["data"] = []

        # Recurse into HasComponent children
        relationships = instance.get("relationships", {})
        composed_of = relationships.get("HasComponent", [])
        if isinstance(composed_of, str):
            composed_of = [composed_of]

        if (max_depth == 0 or max_depth > 1) and composed_of:
            next_max_depth = 0 if max_depth == 0 else max_depth - 1
            for child_id in composed_of:
                child_result = self._get_values_recursive(child_id, startTime, endTime, returnHistory, next_max_depth)
                if child_result is not None:
                    inner_result[child_id] = child_result.get(child_id, {})

        return {element_id: inner_result}

    def _get_raw_value(self, instance: Dict[str, Any]) -> Any:
        """Extract the actual value payload for an instance."""
        type_eid = instance.get("typeElementId")

        if type_eid == "aas-shell-type":
            # For shells, return a summary extracted from the raw shell payload
            raw = instance.get("_raw", {})
            return {
                "idShort": raw.get("idShort"),
                "id": raw.get("id", raw.get("identification")),
                "assetInformation": raw.get("assetInformation"),
            }

        if type_eid == "aas-submodel-type":
            aas_id = instance.get("_aasId")
            sm_id = instance.get("_submodelId")
            if aas_id and sm_id:
                return self._fetch_submodel_value(aas_id, sm_id)
            return None

        # Virtual instances may carry a static _value
        if "_value" in instance:
            return instance["_value"]

        # Folder types and other virtual objects without explicit values
        if type_eid == "folder-type":
            return {
                "name": instance.get("displayName"),
                "description": instance.get("description", ""),
            }

        return None

    # ------------------------------------------------------------------
    # I3XDataSource interface: relationships
    # ------------------------------------------------------------------

    def get_related_instances(
        self, element_id: str, relationship_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        instance = self.get_instance_by_id(element_id, values=True)
        if not instance:
            return []

        relationships = instance.get("relationships", {})
        related = []
        seen = set()

        if relationship_type is None:
            # Return all related instances
            for rel_type, related_ids in relationships.items():
                if isinstance(related_ids, str):
                    related_ids = [related_ids]
                for rid in related_ids:
                    if rid in seen:
                        continue
                    rel_instance = self.get_instance_by_id(rid)
                    if rel_instance:
                        rel_instance = dict(rel_instance)
                        rel_instance["sourceRelationship"] = rel_type
                        related.append(rel_instance)
                        seen.add(rid)
        else:
            # Case-insensitive match on relationship type
            matching_key = None
            for key in relationships:
                if key.lower() == relationship_type.lower():
                    matching_key = key
                    break
            if matching_key:
                related_ids = relationships[matching_key]
                if isinstance(related_ids, str):
                    related_ids = [related_ids]
                for rid in related_ids:
                    rel_instance = self.get_instance_by_id(rid)
                    if rel_instance:
                        rel_instance = dict(rel_instance)
                        rel_instance["sourceRelationship"] = matching_key
                        related.append(rel_instance)

        return related

    # ------------------------------------------------------------------
    # I3XDataSource interface: updates (read-only — not supported)
    # ------------------------------------------------------------------

    def update_instance_value(self, element_id: str, value: Any) -> Dict[str, Any]:
        return {
            "elementId": element_id,
            "success": False,
            "message": "AAS viewer data source is read-only",
        }

    # ------------------------------------------------------------------
    # I3XDataSource interface: extra attributes
    # ------------------------------------------------------------------

    def get_instance_extra_attributes(self, element_id: str) -> Optional[Dict[str, Any]]:
        instance = self.get_instance_by_id(element_id)
        if not instance:
            return None
        # AAS instances are fully described by their type schemas
        return {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_internal(instance: Dict[str, Any]) -> Dict[str, Any]:
        """Remove internal keys (prefixed with _) before returning to callers."""
        return {k: v for k, v in instance.items() if not k.startswith("_")}
