# Static i3X definitions for the AAS (Asset Administration Shell) adapter.
# These define the namespace, object types, and relationship types that
# frame AAS Shells and Submodels within the i3X address space.

AAS_NAMESPACE_URI = "https://admin-shell.io/aas/3/0"
DEMO_NAMESPACE_URI = "https://cesmii.org/i3x/demo"

AAS_DATA = {
    "namespaces": [
        {
            "uri": AAS_NAMESPACE_URI,
            "displayName": "Asset Administration Shell",
        },
        {
            "uri": DEMO_NAMESPACE_URI,
            "displayName": "i3X Demo",
        },
    ],
    "objectTypes": [
        {
            "elementId": "aas-shell-type",
            "displayName": "AAS Shell",
            "namespaceUri": AAS_NAMESPACE_URI,
            "sourceTypeId": "AssetAdministrationShell",
            "schema": {
                "type": "object",
                "description": "An Asset Administration Shell representing a digital twin of a physical or logical asset.",
                "properties": {
                    "idShort": {"type": "string", "description": "Short identifier of the shell"},
                    "id": {"type": "string", "description": "Globally unique identifier of the shell"},
                    "assetInformation": {
                        "type": "object",
                        "description": "Information about the asset this shell represents",
                        "properties": {
                            "assetKind": {"type": "string"},
                            "globalAssetId": {"type": "string"},
                        },
                    },
                },
            },
            "related": {
                "relationshipType": "HasComponent",
                "types": [f"{AAS_NAMESPACE_URI}:aas-submodel-type"],
            },
        },
        {
            "elementId": "aas-submodel-type",
            "displayName": "AAS Submodel",
            "namespaceUri": AAS_NAMESPACE_URI,
            "sourceTypeId": "Submodel",
            "schema": {
                "type": "object",
                "description": "A Submodel containing structured data about one aspect of an asset.",
                "properties": {
                    "idShort": {"type": "string", "description": "Short identifier of the submodel"},
                    "id": {"type": "string", "description": "Globally unique identifier of the submodel"},
                    "semanticId": {"type": "string", "description": "Semantic identifier referencing the submodel template"},
                    "submodelElements": {
                        "type": "array",
                        "description": "The submodel element collection",
                    },
                },
            },
        },
        {
            "elementId": "folder-type",
            "displayName": "Folder",
            "namespaceUri": DEMO_NAMESPACE_URI,
            "sourceTypeId": "Folder",
            "schema": {
                "type": "object",
                "description": "A virtual organizational container for grouping objects.",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            "related": {
                "relationshipType": "HasChildren",
            },
        },
        {
            "elementId": "ev-type",
            "displayName": "EVType",
            "namespaceUri": DEMO_NAMESPACE_URI,
            "sourceTypeId": "EVType",
            "schema": {
                "type": "object",
                "description": "An electric vehicle model.",
                "properties": {
                    "manufacturer": {"type": "string"},
                    "model": {"type": "string"},
                },
            },
        },
    ],
    "relationshipTypes": [
        {
            "elementId": "HasParent",
            "displayName": "HasParent",
            "namespaceUri": "https://cesmii.org/i3x",
            "relationshipId": "HasParent",
            "reverseOf": "HasChildren",
        },
        {
            "elementId": "HasChildren",
            "displayName": "HasChildren",
            "namespaceUri": "https://cesmii.org/i3x",
            "relationshipId": "HasChildren",
            "reverseOf": "HasParent",
        },
        {
            "elementId": "HasComponent",
            "displayName": "HasComponent",
            "namespaceUri": "https://cesmii.org/i3x",
            "relationshipId": "HasComponent",
            "reverseOf": "ComponentOf",
        },
        {
            "elementId": "ComponentOf",
            "displayName": "ComponentOf",
            "namespaceUri": "https://cesmii.org/i3x",
            "relationshipId": "ComponentOf",
            "reverseOf": "HasComponent",
        },
        # Graph relationships linking physical assets to their digital passports
        {
            "elementId": "HasDigitalPassport",
            "displayName": "HasDigitalPassport",
            "namespaceUri": DEMO_NAMESPACE_URI,
            "relationshipId": "HasDigitalPassport",
            "reverseOf": "DigitalPassportOf",
        },
        {
            "elementId": "DigitalPassportOf",
            "displayName": "DigitalPassportOf",
            "namespaceUri": DEMO_NAMESPACE_URI,
            "relationshipId": "DigitalPassportOf",
            "reverseOf": "HasDigitalPassport",
        },
    ],
}

# Virtual instances defined statically. These are merged into the instance
# cache at startup alongside the dynamically-fetched AAS shells/submodels.
VIRTUAL_INSTANCES = [
    {
        "elementId": "i3x-explained",
        "displayName": "i3X Explained",
        "description": "An overview of the Industrial Information Interface eXchange",
        "typeElementId": "folder-type",
        "parentId": None,
        "isComposition": False,
        "relationships": {},
        "_value": (
            "i3X is Industrial Information Interoperability eXchange, from CESMII.\r\n"
            "This effort specifies a common API definition for conextualized manufacturing information. "
            "When platforms share a common data structure, like a Digital Passport, i3X makes it easy "
            "to share, and interoperate on that information. This common client, i3X Explorer illustrates "
            "how the common API can be visualized consistently. Other vendors at Hannover Messe have i3X "
            "running in their booths. Visit HighByte, Inductive Automation, Prosys and anywhere else you "
            "see the i3X badge, for more information!"
        ),
    },
    {
        "elementId": "digital-passports",
        "displayName": "Digital Passports",
        "description": "Collection of Asset Administration Shell digital passports",
        "typeElementId": "folder-type",
        "parentId": None,
        "isComposition": False,
        "relationships": {
            # HasChildren populated dynamically with all shell element IDs
        },
    },
    {
        "elementId": "electric-vehicles",
        "displayName": "Electric Vehicles",
        "description": "Electric vehicle models",
        "typeElementId": "folder-type",
        "parentId": None,
        "isComposition": False,
        "relationships": {
            "HasChildren": [
                "ev-mercedes-eqs",
                "ev-renault-zoe",
                "ev-fiat-grande-panda",
                "ev-toyota-urban-cruiser",
            ],
        },
    },
    {
        "elementId": "ev-mercedes-eqs",
        "displayName": "Mercedes EQS",
        "description": "Mercedes-Benz EQS electric sedan",
        "typeElementId": "ev-type",
        "parentId": "electric-vehicles",
        "isComposition": False,
        "relationships": {
            "HasParent": "electric-vehicles",
        },
        "_value": {"manufacturer": "Mercedes-Benz", "model": "EQS"},
        "_linkedAasId": "https://batterypass.twinsphere.io/imxdemo/aas/DEMO-MB-EQS-BP-108-001234",
    },
    {
        "elementId": "ev-renault-zoe",
        "displayName": "Renault Zoe",
        "description": "Renault Zoe electric hatchback",
        "typeElementId": "ev-type",
        "parentId": "electric-vehicles",
        "isComposition": False,
        "relationships": {
            "HasParent": "electric-vehicles",
        },
        "_value": {"manufacturer": "Renault", "model": "Zoe"},
        "_linkedAasId": "https://batterypass.twinsphere.io/imxdemo/aas/DEMO-RNO-ZOE-BP-052-00912",
    },
    {
        "elementId": "ev-fiat-grande-panda",
        "displayName": "Fiat Grande Panda",
        "description": "Fiat Grande Panda electric city car",
        "typeElementId": "ev-type",
        "parentId": "electric-vehicles",
        "isComposition": False,
        "relationships": {
            "HasParent": "electric-vehicles",
        },
        "_value": {"manufacturer": "Fiat", "model": "Grande Panda"},
        "_linkedAasId": "https://batterypass.twinsphere.io/imxdemo/aas/DEMO-FIA-GP-E-BP-044-00456",
    },
    {
        "elementId": "ev-toyota-urban-cruiser",
        "displayName": "Toyota Urban Cruiser",
        "description": "Toyota Urban Cruiser electric SUV",
        "typeElementId": "ev-type",
        "parentId": "electric-vehicles",
        "isComposition": False,
        "relationships": {
            "HasParent": "electric-vehicles",
        },
        "_value": {"manufacturer": "Toyota", "model": "Urban Cruiser"},
        "_linkedAasId": "https://batterypass.twinsphere.io/imxdemo/aas/DEMO-TYT-UC-BP-061-0076001",
    },
]
