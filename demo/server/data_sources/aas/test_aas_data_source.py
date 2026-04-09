"""Unit tests for the AAS data source adapter.

Tests the AASDataSource in isolation by mocking HTTP responses from the
TwinSphere API. No live network calls are made.
"""

import base64
import json
import unittest
from unittest.mock import MagicMock, patch

from .aas_data_source import AASDataSource
from .aas_data import AAS_NAMESPACE_URI, DEMO_NAMESPACE_URI


# ---------------------------------------------------------------------------
# Test fixtures — representative AAS API responses
# ---------------------------------------------------------------------------

# AAS ID that matches the Mercedes EQS _linkedAasId in VIRTUAL_INSTANCES
LINKED_AAS_ID = "https://batterypass.twinsphere.io/imxdemo/aas/DEMO-MB-EQS-BP-108-001234"

SAMPLE_SHELLS = [
    {
        "id": "urn:example:aas:pump-001",
        "idShort": "Pump001",
        "description": [{"language": "en", "text": "Primary coolant pump"}],
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": "urn:example:asset:pump-001",
        },
    },
    {
        "id": "urn:example:aas:valve-002",
        "idShort": "Valve002",
        "description": "Pressure relief valve",
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": "urn:example:asset:valve-002",
        },
    },
    {
        "id": LINKED_AAS_ID,
        "idShort": "DEMO-MB-EQS-BP-108-001234",
        "description": "Mercedes EQS Battery Passport",
        "assetInformation": {
            "assetKind": "Instance",
            "globalAssetId": "urn:batterypass:mb-eqs-001234",
        },
    },
]

SAMPLE_SUBMODEL_REFS_PUMP = [
    {
        "type": "ModelReference",
        "referredSemanticId": "urn:example:sm:nameplate",
        "keys": [{"type": "Submodel", "value": "urn:example:sm:pump-001-nameplate"}],
    },
    {
        "type": "ModelReference",
        "referredSemanticId": "urn:example:sm:opdata",
        "keys": [{"type": "Submodel", "value": "urn:example:sm:pump-001-opdata"}],
    },
]

SAMPLE_SUBMODEL_REFS_VALVE = [
    {
        "type": "ModelReference",
        "keys": [{"type": "Submodel", "value": "urn:example:sm:valve-002-nameplate"}],
    },
]

SAMPLE_SUBMODEL_CONTENT = {
    "idShort": "Nameplate",
    "id": "urn:example:sm:pump-001-nameplate",
    "submodelElements": [
        {"idShort": "ManufacturerName", "value": "AcmePumps"},
        {"idShort": "SerialNumber", "value": "SN-12345"},
    ],
}


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode("ascii")


def _mock_httpx_get(url, params=None):
    """Route mock GET requests to return test fixtures."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()

    if "/api/ShellList" in str(url):
        resp.json.return_value = SAMPLE_SHELLS
        return resp

    # Submodel refs for each shell
    b64_pump = _b64("urn:example:aas:pump-001")
    b64_valve = _b64("urn:example:aas:valve-002")
    b64_linked = _b64(LINKED_AAS_ID)

    if f"/api/submodels/{b64_pump}" in str(url) and "/submodel/" not in str(url):
        resp.json.return_value = SAMPLE_SUBMODEL_REFS_PUMP
        return resp
    if f"/api/submodels/{b64_valve}" in str(url) and "/submodel/" not in str(url):
        resp.json.return_value = SAMPLE_SUBMODEL_REFS_VALVE
        return resp
    if f"/api/submodels/{b64_linked}" in str(url) and "/submodel/" not in str(url):
        resp.json.return_value = []  # no submodels for the battery passport shell
        return resp

    # Full submodel content
    if "/submodel/" in str(url):
        resp.json.return_value = SAMPLE_SUBMODEL_CONTENT
        return resp

    resp.json.return_value = {}
    return resp


class TestAASDataSource(unittest.TestCase):
    """Tests for AASDataSource with mocked HTTP."""

    @classmethod
    def setUpClass(cls):
        cls.ds = AASDataSource({"base_url": "https://fake.example.com"})
        # Patch the httpx client
        mock_client = MagicMock()
        mock_client.get = _mock_httpx_get
        cls.ds._client = mock_client
        cls.ds._load_shells()

        # Precompute expected element IDs
        cls.shell_pump_eid = AASDataSource._element_id_for_shell("urn:example:aas:pump-001")
        cls.shell_valve_eid = AASDataSource._element_id_for_shell("urn:example:aas:valve-002")
        cls.sm_nameplate_eid = AASDataSource._element_id_for_submodel(
            "urn:example:aas:pump-001", "urn:example:sm:pump-001-nameplate"
        )
        cls.sm_opdata_eid = AASDataSource._element_id_for_submodel(
            "urn:example:aas:pump-001", "urn:example:sm:pump-001-opdata"
        )

    # -- Namespaces --------------------------------------------------------

    def test_namespaces(self):
        ns = self.ds.get_namespaces()
        self.assertEqual(len(ns), 2)
        uris = {n["uri"] for n in ns}
        self.assertIn(AAS_NAMESPACE_URI, uris)
        self.assertIn(DEMO_NAMESPACE_URI, uris)

    # -- Object Types ------------------------------------------------------

    def test_object_types_all(self):
        types = self.ds.get_object_types()
        self.assertEqual(len(types), 4)
        ids = {t["elementId"] for t in types}
        self.assertSetEqual(ids, {"aas-shell-type", "aas-submodel-type", "folder-type", "ev-type"})

    def test_object_types_filter_by_namespace(self):
        aas_types = self.ds.get_object_types(namespace_uri=AAS_NAMESPACE_URI)
        self.assertEqual(len(aas_types), 2)
        demo_types = self.ds.get_object_types(namespace_uri=DEMO_NAMESPACE_URI)
        self.assertEqual(len(demo_types), 2)
        types_none = self.ds.get_object_types(namespace_uri="urn:nonexistent")
        self.assertEqual(len(types_none), 0)

    def test_object_type_by_id(self):
        t = self.ds.get_object_type_by_id("aas-shell-type")
        self.assertIsNotNone(t)
        self.assertEqual(t["displayName"], "AAS Shell")
        t2 = self.ds.get_object_type_by_id("ev-type")
        self.assertIsNotNone(t2)
        self.assertEqual(t2["displayName"], "EVType")
        self.assertIsNone(self.ds.get_object_type_by_id("nonexistent"))

    # -- Relationship Types ------------------------------------------------

    def test_relationship_types(self):
        rts = self.ds.get_relationship_types()
        self.assertEqual(len(rts), 6)
        ids = {r["elementId"] for r in rts}
        self.assertSetEqual(ids, {
            "HasParent", "HasChildren", "HasComponent", "ComponentOf",
            "HasDigitalPassport", "DigitalPassportOf",
        })

    def test_relationship_type_by_id(self):
        rt = self.ds.get_relationship_type_by_id("HasComponent")
        self.assertIsNotNone(rt)
        self.assertEqual(rt["reverseOf"], "ComponentOf")

    # -- Instances ---------------------------------------------------------

    def test_instances_total_count(self):
        """3 shells + 3 submodels + 3 folders (incl i3X Explained) + 4 EVs = 13 instances"""
        instances = self.ds.get_instances()
        self.assertEqual(len(instances), 13)

    def test_instances_root_only(self):
        """Three roots: i3X Explained, Digital Passports, Electric Vehicles."""
        roots = self.ds.get_instances(root=True)
        self.assertEqual(len(roots), 3)
        names = {r["displayName"] for r in roots}
        self.assertSetEqual(names, {"i3X Explained", "Digital Passports", "Electric Vehicles"})
        for r in roots:
            self.assertIsNone(r.get("parentId"))

    def test_instances_filter_by_type(self):
        shells = self.ds.get_instances(type_id="aas-shell-type")
        self.assertEqual(len(shells), 3)
        submodels = self.ds.get_instances(type_id="aas-submodel-type")
        self.assertEqual(len(submodels), 3)
        folders = self.ds.get_instances(type_id="folder-type")
        self.assertEqual(len(folders), 3)
        evs = self.ds.get_instances(type_id="ev-type")
        self.assertEqual(len(evs), 4)

    def test_shells_parented_under_digital_passports(self):
        """All shells should be children of Digital Passports."""
        shell_pump = self.ds.get_instance_by_id(self.shell_pump_eid)
        self.assertEqual(shell_pump["parentId"], "digital-passports")
        shell_valve = self.ds.get_instance_by_id(self.shell_valve_eid)
        self.assertEqual(shell_valve["parentId"], "digital-passports")

    def test_digital_passports_has_children(self):
        dp = self.ds.get_instance_by_id("digital-passports", values=True)
        children = dp["relationships"]["HasChildren"]
        self.assertIn(self.shell_pump_eid, children)
        self.assertIn(self.shell_valve_eid, children)
        self.assertEqual(len(children), 3)

    def test_evs_parented_under_electric_vehicles(self):
        for ev_id in ["ev-mercedes-eqs", "ev-renault-zoe", "ev-fiat-grande-panda", "ev-toyota-urban-cruiser"]:
            inst = self.ds.get_instance_by_id(ev_id)
            self.assertIsNotNone(inst, f"{ev_id} not found")
            self.assertEqual(inst["parentId"], "electric-vehicles")
            self.assertEqual(inst["typeElementId"], "ev-type")

    def test_electric_vehicles_has_children(self):
        ev_folder = self.ds.get_instance_by_id("electric-vehicles", values=True)
        children = ev_folder["relationships"]["HasChildren"]
        self.assertEqual(len(children), 4)

    def test_instance_by_id_shell(self):
        inst = self.ds.get_instance_by_id(self.shell_pump_eid)
        self.assertIsNotNone(inst)
        self.assertEqual(inst["displayName"], "Pump001")
        self.assertEqual(inst["typeElementId"], "aas-shell-type")
        self.assertTrue(inst["isComposition"])
        # Internal keys should be stripped
        self.assertNotIn("_raw", inst)
        self.assertNotIn("_aasId", inst)

    def test_instance_by_id_submodel(self):
        inst = self.ds.get_instance_by_id(self.sm_nameplate_eid)
        self.assertIsNotNone(inst)
        self.assertEqual(inst["typeElementId"], "aas-submodel-type")
        self.assertEqual(inst["parentId"], self.shell_pump_eid)

    def test_instance_by_id_not_found(self):
        self.assertIsNone(self.ds.get_instance_by_id("nonexistent"))

    def test_internal_keys_stripped(self):
        for inst in self.ds.get_all_instances():
            for key in inst:
                self.assertFalse(key.startswith("_"), f"Internal key '{key}' leaked")

    # -- Relationships -----------------------------------------------------

    def test_shell_has_component(self):
        related = self.ds.get_related_instances(self.shell_pump_eid, "HasComponent")
        self.assertEqual(len(related), 2)
        eids = {r["elementId"] for r in related}
        self.assertIn(self.sm_nameplate_eid, eids)
        self.assertIn(self.sm_opdata_eid, eids)

    def test_shell_has_parent(self):
        related = self.ds.get_related_instances(self.shell_pump_eid, "HasParent")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["elementId"], "digital-passports")

    def test_submodel_component_of(self):
        related = self.ds.get_related_instances(self.sm_nameplate_eid, "ComponentOf")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["elementId"], self.shell_pump_eid)

    def test_related_all(self):
        related = self.ds.get_related_instances(self.shell_pump_eid)
        self.assertGreater(len(related), 0)
        for r in related:
            self.assertIn("sourceRelationship", r)

    def test_related_not_found(self):
        related = self.ds.get_related_instances("nonexistent")
        self.assertEqual(related, [])

    # -- Graph relationships (HasDigitalPassport / DigitalPassportOf) -------

    def test_ev_has_digital_passport(self):
        """Mercedes EQS should link to its battery passport shell."""
        related = self.ds.get_related_instances("ev-mercedes-eqs", "HasDigitalPassport")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["typeElementId"], "aas-shell-type")
        self.assertEqual(related[0]["displayName"], "DEMO-MB-EQS-BP-108-001234")
        self.assertEqual(related[0]["sourceRelationship"], "HasDigitalPassport")

    def test_shell_digital_passport_of(self):
        """The linked shell should have a reverse DigitalPassportOf back to the EV."""
        linked_shell_eid = AASDataSource._element_id_for_shell(LINKED_AAS_ID)
        related = self.ds.get_related_instances(linked_shell_eid, "DigitalPassportOf")
        self.assertEqual(len(related), 1)
        self.assertEqual(related[0]["elementId"], "ev-mercedes-eqs")
        self.assertEqual(related[0]["sourceRelationship"], "DigitalPassportOf")

    def test_ev_without_matching_shell_no_crash(self):
        """EVs whose linked AAS ID isn't in the shell list should still work (no HasDigitalPassport resolves)."""
        # Renault Zoe links to an AAS ID not in SAMPLE_SHELLS
        related = self.ds.get_related_instances("ev-renault-zoe", "HasDigitalPassport")
        # The relationship exists in data but the target shell wasn't loaded, so get_related returns empty
        # (get_instance_by_id returns None for the unresolved element ID)
        self.assertEqual(len(related), 0)

    # -- Values ------------------------------------------------------------

    def test_shell_value(self):
        result = self.ds.get_instance_values_by_id(self.shell_pump_eid)
        self.assertIsNotNone(result)
        inner = result[self.shell_pump_eid]
        self.assertIn("data", inner)
        vqt = inner["data"][0]
        self.assertEqual(vqt["quality"], "Good")
        self.assertEqual(vqt["value"]["idShort"], "Pump001")

    def test_submodel_value(self):
        result = self.ds.get_instance_values_by_id(self.sm_nameplate_eid)
        self.assertIsNotNone(result)
        inner = result[self.sm_nameplate_eid]
        vqt = inner["data"][0]
        # Should match the mocked submodel content
        self.assertEqual(vqt["value"]["idShort"], "Nameplate")

    def test_ev_value(self):
        result = self.ds.get_instance_values_by_id("ev-mercedes-eqs")
        self.assertIsNotNone(result)
        inner = result["ev-mercedes-eqs"]
        vqt = inner["data"][0]
        self.assertEqual(vqt["value"]["manufacturer"], "Mercedes-Benz")
        self.assertEqual(vqt["value"]["model"], "EQS")

    def test_folder_value(self):
        result = self.ds.get_instance_values_by_id("digital-passports")
        self.assertIsNotNone(result)
        inner = result["digital-passports"]
        vqt = inner["data"][0]
        self.assertEqual(vqt["value"]["name"], "Digital Passports")

    def test_values_with_depth(self):
        """maxDepth=0 (infinite) should include component submodels."""
        result = self.ds.get_instance_values_by_id(self.shell_pump_eid, maxDepth=0)
        inner = result[self.shell_pump_eid]
        # Should have child keys beyond 'data'
        child_keys = [k for k in inner if k != "data"]
        self.assertEqual(len(child_keys), 2)

    def test_values_no_recurse(self):
        """maxDepth=1 (default) should NOT include children."""
        result = self.ds.get_instance_values_by_id(self.shell_pump_eid, maxDepth=1)
        inner = result[self.shell_pump_eid]
        child_keys = [k for k in inner if k != "data"]
        self.assertEqual(len(child_keys), 0)

    def test_values_not_found(self):
        self.assertIsNone(self.ds.get_instance_values_by_id("nonexistent"))

    # -- Updates (read-only) -----------------------------------------------

    def test_update_rejected(self):
        result = self.ds.update_instance_value(self.shell_pump_eid, {"foo": 1})
        self.assertFalse(result["success"])
        self.assertIn("read-only", result["message"])

    # -- Extra attributes --------------------------------------------------

    def test_extra_attributes_empty(self):
        extras = self.ds.get_instance_extra_attributes(self.shell_pump_eid)
        self.assertEqual(extras, {})

    def test_extra_attributes_not_found(self):
        self.assertIsNone(self.ds.get_instance_extra_attributes("nonexistent"))

    # -- Element ID encoding -----------------------------------------------

    def test_element_id_roundtrip(self):
        aas_id = "urn:example:aas:pump-001"
        sm_id = "urn:example:sm:pump-001-nameplate"
        shell_eid = AASDataSource._element_id_for_shell(aas_id)
        sm_eid = AASDataSource._element_id_for_submodel(aas_id, sm_id)

        parsed_shell = self.ds._parse_element_id(shell_eid)
        self.assertEqual(parsed_shell["aasId"], aas_id)
        self.assertIsNone(parsed_shell["submodelId"])

        parsed_sm = self.ds._parse_element_id(sm_eid)
        self.assertEqual(parsed_sm["aasId"], aas_id)
        self.assertEqual(parsed_sm["submodelId"], sm_id)


if __name__ == "__main__":
    unittest.main()
