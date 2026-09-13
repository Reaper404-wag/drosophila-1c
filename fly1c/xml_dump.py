from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from .ir import Attribute, Catalog, ConfigIR, Document, Register, TypeSpec, World

NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
FMT = "2.17"

NSMAP = """xmlns="http://v8.1c.ru/8.3/MDClasses" xmlns:app="http://v8.1c.ru/8.2/managed-application/core" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:cmi="http://v8.1c.ru/8.2/managed-application/cmi" xmlns:ent="http://v8.1c.ru/8.1/data/enterprise" xmlns:lf="http://v8.1c.ru/8.2/managed-application/logform" xmlns:style="http://v8.1c.ru/8.1/data/ui/style" xmlns:sys="http://v8.1c.ru/8.1/data/ui/fonts/system" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:web="http://v8.1c.ru/8.1/data/ui/colors/web" xmlns:win="http://v8.1c.ru/8.1/data/ui/colors/windows" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xpr="http://v8.1c.ru/8.3/xcf/predef" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" """

CONFIG_CLASS_IDS = [
    "9cd510cd-abfc-11d4-9434-004095e12fc7",
    "9fcd25a0-4822-11d4-9414-008048da11f9",
    "e3687481-0a87-462c-a166-9f34594f9bba",
    "9de14907-ec23-4a07-96f0-85521cb6b53b",
    "51f2d5d8-ea4d-4064-8892-82951750031e",
    "e68182ea-4237-4383-967f-90c1e3370bc7",
    "fb282519-d103-4dd3-bc12-cb271d631dfc",
]

MOBILE = [
    ("Biometrics", True), ("Location", False), ("BackgroundLocation", False),
    ("BluetoothPrinters", False), ("WiFiPrinters", False), ("Contacts", False),
    ("Calendars", False), ("PushNotifications", False), ("LocalNotifications", False),
    ("InAppPurchases", False), ("PersonalComputerFileExchange", False), ("Ads", False),
    ("NumberDialing", False), ("CallProcessing", False), ("CallLog", False),
    ("AutoSendSMS", False), ("ReceiveSMS", False), ("SMSLog", False),
    ("Camera", False), ("Microphone", False), ("MusicLibrary", False),
    ("PictureAndVideoLibraries", False), ("AudioPlaybackAndVibration", False),
    ("BackgroundAudioPlaybackAndVibration", False), ("InstallPackages", False),
    ("OSBackup", True), ("ApplicationUsageStatistics", False), ("BarcodeScanning", False),
    ("BackgroundAudioRecording", False), ("AllFilesAccess", False),
    ("Videoconferences", False), ("NFC", False), ("DocumentScanning", False),
    ("SpeechToText", False), ("Geofences", False), ("IncomingShareRequests", False),
    ("AllIncomingShareRequestsTypesProcessing", False),
]


def uid(*parts: str) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


def _syn(text: str | None) -> str:
    if not text:
        return "<Synonym/>"
    return (
        "<Synonym><v8:item><v8:lang>ru</v8:lang>"
        f"<v8:content>{escape(text)}</v8:content></v8:item></Synonym>"
    )


def _type_xml(t: TypeSpec) -> str:
    if t.kind == "String":
        length = 0 if t.unlimited else (t.length or 10)
        return (
            "<Type><v8:Type>xs:string</v8:Type><v8:StringQualifiers>"
            f"<v8:Length>{length}</v8:Length>"
            "<v8:AllowedLength>Variable</v8:AllowedLength>"
            "</v8:StringQualifiers></Type>"
        )
    if t.kind == "Number":
        sign = "Nonnegative" if t.nonnegative else "Any"
        return (
            "<Type><v8:Type>xs:decimal</v8:Type><v8:NumberQualifiers>"
            f"<v8:Digits>{t.digits or 10}</v8:Digits>"
            f"<v8:FractionDigits>{t.fraction or 0}</v8:FractionDigits>"
            f"<v8:AllowedSign>{sign}</v8:AllowedSign>"
            "</v8:NumberQualifiers></Type>"
        )
    if t.kind == "Boolean":
        return "<Type><v8:Type>xs:boolean</v8:Type></Type>"
    if t.kind == "Date":
        frac = t.date_fractions or "Date"
        return (
            "<Type><v8:Type>xs:dateTime</v8:Type><v8:DateQualifiers>"
            f"<v8:DateFractions>{frac}</v8:DateFractions>"
            "</v8:DateQualifiers></Type>"
        )
    if t.kind == "CatalogRef":
        return f"<Type><v8:Type>cfg:CatalogRef.{escape(t.ref or '')}</v8:Type></Type>"
    if t.kind == "EnumRef":
        return f"<Type><v8:Type>cfg:EnumRef.{escape(t.ref or '')}</v8:Type></Type>"
    return "<Type><v8:Type>xs:string</v8:Type></Type>"


def _attr_xml(attr: Attribute, stored: bool = True) -> str:
    extra = ""
    if stored:
        extra = (
            "<Indexing>DontIndex</Indexing><FullTextSearch>Use</FullTextSearch>"
            "<DataHistory>Use</DataHistory>"
        )
    return f"""<Attribute uuid="{uid('attr', attr.name, attr.type.key())}">
<Properties>
<Name>{escape(attr.name)}</Name>
{_syn(attr.synonym or attr.name)}
<Comment/>
{_type_xml(attr.type)}
<PasswordMode>false</PasswordMode>
<Format/><EditFormat/><ToolTip/>
<MarkNegatives>false</MarkNegatives>
<Mask/>
<MultiLine>{"true" if attr.multiline else "false"}</MultiLine>
<ExtendedEdit>{"true" if attr.extended_edit else "false"}</ExtendedEdit>
<MinValue xsi:nil="true"/><MaxValue xsi:nil="true"/>
<FillFromFillingValue>true</FillFromFillingValue>
<FillValue xsi:nil="true"/>
<FillChecking>DontCheck</FillChecking>
<ChoiceFoldersAndItems>Items</ChoiceFoldersAndItems>
<ChoiceParameterLinks/><ChoiceParameters/>
<QuickChoice>Auto</QuickChoice>
<CreateOnInput>Auto</CreateOnInput>
<ChoiceForm/><LinkByType/>
<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
{extra}
</Properties>
</Attribute>"""


def _generated(prefix: str, name: str, categories: list[tuple[str, str]]) -> str:
    chunks = []
    for cat, short in categories:
        chunks.append(
            f'<xr:GeneratedType name="{cat}.{escape(name)}" category="{short}">'
            f"<xr:TypeId>{uid('t', cat, name)}</xr:TypeId>"
            f"<xr:ValueId>{uid('v', cat, name)}</xr:ValueId>"
            "</xr:GeneratedType>"
        )
    return "<InternalInfo>" + "".join(chunks) + "</InternalInfo>"


def _ts_xml(owner_kind: str, owner: str, ts) -> str:
    children = "".join(_attr_xml(a) for a in ts.attributes)
    gen = (
        "<InternalInfo>"
        f'<xr:GeneratedType name="{owner_kind}TabularSection.{escape(owner)}.{escape(ts.name)}" category="TabularSection">'
        f"<xr:TypeId>{uid('ts', owner, ts.name)}</xr:TypeId>"
        f"<xr:ValueId>{uid('tsv', owner, ts.name)}</xr:ValueId></xr:GeneratedType>"
        f'<xr:GeneratedType name="{owner_kind}TabularSectionRow.{escape(owner)}.{escape(ts.name)}" category="TabularSectionRow">'
        f"<xr:TypeId>{uid('tsr', owner, ts.name)}</xr:TypeId>"
        f"<xr:ValueId>{uid('tsrv', owner, ts.name)}</xr:ValueId></xr:GeneratedType>"
        "</InternalInfo>"
    )
    return f"""<TabularSection uuid="{uid('tab', owner, ts.name)}">
{gen}
<Properties>
<Name>{escape(ts.name)}</Name>
{_syn(ts.synonym or ts.name)}
<Comment/><ToolTip/>
<FillChecking>DontCheck</FillChecking>
</Properties>
<ChildObjects>{children}</ChildObjects>
</TabularSection>"""


SEED_MODULE = "ЗагрузкаДанных"


def _write_common_module(world: World, out: Path) -> None:
    """Общий серверный модуль с заполнением данных + модуль управляемого приложения."""
    from .seed_bsl import application_module, common_module

    _write(
        out / "CommonModules" / f"{SEED_MODULE}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<CommonModule uuid="{uid('commonmodule', SEED_MODULE)}">
<Properties>
<Name>{SEED_MODULE}</Name>
{_syn(SEED_MODULE)}
<Comment/>
<Global>false</Global>
<ClientManagedApplication>false</ClientManagedApplication>
<Server>true</Server>
<ExternalConnection>false</ExternalConnection>
<ClientOrdinaryApplication>false</ClientOrdinaryApplication>
<ServerCall>true</ServerCall>
<Privileged>true</Privileged>
</Properties>
</CommonModule>
</MetaDataObject>
""",
    )
    mdir = out / "CommonModules" / SEED_MODULE / "Ext"
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "Module.bsl").write_text("﻿" + common_module(world), encoding="utf-8")
    ext = out / "Ext"
    ext.mkdir(parents=True, exist_ok=True)
    (ext / "ManagedApplicationModule.bsl").write_text(
        "﻿" + application_module(), encoding="utf-8"
    )


def dump_world(world: World, out: Path) -> Path:
    cfg = world.config
    out.mkdir(parents=True, exist_ok=True)
    _write_configuration(cfg, out)
    _write_language(out)
    _write_role(cfg, out)
    for sub in cfg.subsystems.values():
        _write_subsystem(cfg, sub, out)
    for cat in cfg.catalogs.values():
        _write_catalog(cat, out)
    for en in cfg.enums.values():
        _write_enum(en, out)
    for doc in cfg.documents.values():
        _write_document(doc, out)
    for reg in cfg.registers.values():
        _write_register(reg, out)
    for rep in cfg.reports.values():
        _write_report(rep, out)
    _write_common_module(world, out)
    _write_dump_info(cfg, out)
    _write_ib_seed(world, out)
    return out


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + body, encoding="utf-8")


def _write_configuration(cfg: ConfigIR, out: Path) -> None:
    contained = []
    for i, cid in enumerate(CONFIG_CLASS_IDS):
        contained.append(
            "<xr:ContainedObject>"
            f"<xr:ClassId>{cid}</xr:ClassId>"
            f"<xr:ObjectId>{uid('cfg', cfg.name, str(i))}</xr:ObjectId>"
            "</xr:ContainedObject>"
        )
    mobile = "".join(
        "<app:functionality>"
        f"<app:functionality>{n}</app:functionality>"
        f"<app:use>{str(u).lower()}</app:use>"
        "</app:functionality>"
        for n, u in MOBILE
    )
    children = ["<Language>Русский</Language>"]
    for name in cfg.subsystem_order or cfg.subsystems:
        children.append(f"<Subsystem>{escape(name)}</Subsystem>")
    children.append(f"<CommonModule>{SEED_MODULE}</CommonModule>")
    children.append("<Role>ПолныеПрава</Role>")
    for name in sorted(cfg.catalogs):
        children.append(f"<Catalog>{escape(name)}</Catalog>")
    for name in sorted(cfg.documents):
        children.append(f"<Document>{escape(name)}</Document>")
    for name in sorted(cfg.enums):
        children.append(f"<Enum>{escape(name)}</Enum>")
    for name in sorted(cfg.reports):
        children.append(f"<Report>{escape(name)}</Report>")
    for name in sorted(cfg.registers):
        children.append(f"<AccumulationRegister>{escape(name)}</AccumulationRegister>")
    body = f"""<MetaDataObject {NSMAP}version="{FMT}">
<Configuration uuid="{uid('configuration', cfg.name)}">
<InternalInfo>{''.join(contained)}</InternalInfo>
<Properties>
<Name>{escape(cfg.name)}</Name>
{_syn(cfg.synonym or cfg.name)}
<Comment/><NamePrefix/>
<ConfigurationExtensionCompatibilityMode>Version8_3_24</ConfigurationExtensionCompatibilityMode>
<DefaultRunMode>ManagedApplication</DefaultRunMode>
<UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes>
<ScriptVariant>Russian</ScriptVariant>
<DefaultRoles><xr:Item xsi:type="xr:MDObjectRef">Role.ПолныеПрава</xr:Item></DefaultRoles>
<Vendor/><Version/><UpdateCatalogAddress/>
<IncludeHelpInContents>false</IncludeHelpInContents>
<UseManagedFormInOrdinaryApplication>false</UseManagedFormInOrdinaryApplication>
<UseOrdinaryFormInManagedApplication>false</UseOrdinaryFormInManagedApplication>
<AdditionalFullTextSearchDictionaries/>
<CommonSettingsStorage/><ReportsUserSettingsStorage/><ReportsVariantsStorage/>
<FormDataSettingsStorage/><DynamicListsUserSettingsStorage/><URLExternalDataStorage/>
<Content/>
<DefaultReportForm/><DefaultReportVariantForm/><DefaultReportSettingsForm/>
<DefaultReportAppearanceTemplate/><DefaultDynamicListSettingsForm/><DefaultSearchForm/>
<DefaultDataHistoryChangeHistoryForm/><DefaultDataHistoryVersionDataForm/>
<DefaultDataHistoryVersionDifferencesForm/><DefaultCollaborationSystemUsersChoiceForm/>
<RequiredMobileApplicationPermissions/>
<UsedMobileApplicationFunctionalities>{mobile}</UsedMobileApplicationFunctionalities>
<StandaloneConfigurationRestrictionRoles/><MobileApplicationURLs/>
<AllowedIncomingShareRequestTypes/>
<MainClientApplicationWindowMode>Normal</MainClientApplicationWindowMode>
<DefaultInterface/><DefaultStyle/>
<DefaultLanguage>Language.Русский</DefaultLanguage>
<BriefInformation/><DetailedInformation/><Copyright/>
<VendorInformationAddress/><ConfigurationInformationAddress/>
<DataLockControlMode>Managed</DataLockControlMode>
<ObjectAutonumerationMode>NotAutoFree</ObjectAutonumerationMode>
<ModalityUseMode>DontUse</ModalityUseMode>
<SynchronousPlatformExtensionAndAddInCallUseMode>DontUse</SynchronousPlatformExtensionAndAddInCallUseMode>
<InterfaceCompatibilityMode>Taxi</InterfaceCompatibilityMode>
<DatabaseTablespacesUseMode>DontUse</DatabaseTablespacesUseMode>
<CompatibilityMode>Version8_3_22</CompatibilityMode>
<DefaultConstantsForm/>
</Properties>
<ChildObjects>{''.join(children)}</ChildObjects>
</Configuration>
</MetaDataObject>
"""
    _write(out / "Configuration.xml", body)
    order = "".join(f"<Subsystem>Subsystem.{escape(n)}</Subsystem>" for n in (cfg.subsystem_order or cfg.subsystems))
    (out / "Ext").mkdir(exist_ok=True)
    (out / "Ext" / "CommandInterface.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<CommandInterface xmlns="http://v8.1c.ru/8.3/xcf/extrnprops" xmlns:xr="http://v8.1c.ru/8.3/xcf/readable" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="{FMT}">
<SubsystemsOrder>{order}</SubsystemsOrder>
</CommandInterface>
""",
        encoding="utf-8",
    )


def _write_language(out: Path) -> None:
    _write(
        out / "Languages" / "Русский.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Language uuid="{uid('lang', 'ru')}">
<Properties>
<Name>Русский</Name>
{_syn("Русский")}
<Comment/>
<LanguageCode>ru</LanguageCode>
</Properties>
</Language>
</MetaDataObject>
""",
    )


def _write_role(cfg: ConfigIR, out: Path) -> None:
    _write(
        out / "Roles" / "ПолныеПрава.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Role uuid="{uid('role', 'ПолныеПрава')}">
<Properties>
<Name>ПолныеПрава</Name>
{_syn("Полные права")}
<Comment/>
</Properties>
</Role>
</MetaDataObject>
""",
    )
    rights = f"""<?xml version="1.0" encoding="UTF-8"?>
<Rights xmlns="http://v8.1c.ru/8.2/roles" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:type="Rights" version="{FMT}">
<setForNewObjects>true</setForNewObjects>
<setForAttributesByDefault>true</setForAttributesByDefault>
<independentRightsOfChildObjects>false</independentRightsOfChildObjects>
<object>
<name>Configuration.{escape(cfg.name)}</name>
<right><name>ThinClient</name><value>true</value></right>
<right><name>WebClient</name><value>true</value></right>
<right><name>ThickClientManagedApplication</name><value>true</value></right>
<right><name>ThickClientOrdinaryApplication</name><value>true</value></right>
<right><name>ExternalConnection</name><value>true</value></right>
<right><name>Automation</name><value>true</value></right>
<right><name>UpdateDataBaseConfiguration</name><value>true</value></right>
<right><name>Administration</name><value>true</value></right>
<right><name>DataAdministration</name><value>true</value></right>
<right><name>InteractiveOpenExtDataProcessors</name><value>true</value></right>
<right><name>InteractiveOpenExtReports</name><value>true</value></right>
</object>
</Rights>
"""
    p = out / "Roles" / "ПолныеПрава" / "Ext" / "Rights.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(rights, encoding="utf-8")


def _write_subsystem(cfg: ConfigIR, sub, out: Path) -> None:
    content = "".join(
        f'<xr:Item xsi:type="xr:MDObjectRef">{escape(item)}</xr:Item>' for item in sub.content
    )
    parent = f"<Parent>Subsystem.{escape(sub.parent)}</Parent>" if sub.parent else "<Parent/>"
    _write(
        out / "Subsystems" / f"{sub.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Subsystem uuid="{uid('sub', sub.name)}">
<Properties>
<Name>{escape(sub.name)}</Name>
{_syn(sub.synonym or sub.name)}
<Comment/>
<IncludeHelpInContents>true</IncludeHelpInContents>
<IncludeInCommandInterface>true</IncludeInCommandInterface>
<Explanation/>
<Picture/>
{parent}
<Content>{content}</Content>
</Properties>
<ChildObjects/>
</Subsystem>
</MetaDataObject>
""",
    )


def _write_catalog(cat: Catalog, out: Path) -> None:
    cats = [
        ("CatalogObject", "Object"),
        ("CatalogRef", "Ref"),
        ("CatalogSelection", "Selection"),
        ("CatalogList", "List"),
        ("CatalogManager", "Manager"),
    ]
    children = "".join(_attr_xml(a) for a in cat.attributes)
    children += "".join(_ts_xml("Catalog", cat.name, ts) for ts in cat.tabular_sections)
    children += "".join(f"<Form>{escape(f.name)}</Form>" for f in cat.forms)
    hier = (
        f"<Hierarchical>{str(cat.hierarchical).lower()}</Hierarchical>"
        f"<HierarchyType>{cat.hierarchy_type}</HierarchyType>"
        if cat.hierarchical
        else "<Hierarchical>false</Hierarchical><HierarchyType>HierarchyFoldersAndItems</HierarchyType>"
    )
    desc_syn = ""
    if cat.description_synonym:
        desc_syn = (
            "<StandardAttributes><xr:StandardAttribute name=\"Description\">"
            f"{_syn(cat.description_synonym).replace('Synonym', 'xr:Synonym')}"
            "</xr:StandardAttribute></StandardAttributes>"
        )
    body = f"""<MetaDataObject {NSMAP}version="{FMT}">
<Catalog uuid="{uid('cat', cat.name)}">
{_generated('Catalog', cat.name, cats)}
<Properties>
<Name>{escape(cat.name)}</Name>
{_syn(cat.synonym or cat.name)}
<Comment/>
{hier}
<LimitLevelCount>false</LimitLevelCount>
<LevelCount>2</LevelCount>
<FoldersOnTop>true</FoldersOnTop>
<UseStandardCommands>true</UseStandardCommands>
<Owners/><SubordinationUse>ToItems</SubordinationUse>
<CodeLength>9</CodeLength>
<DescriptionLength>{cat.description_length}</DescriptionLength>
<CodeType>String</CodeType>
<CodeAllowedLength>Variable</CodeAllowedLength>
<CodeSeries>WholeCatalog</CodeSeries>
<CheckUnique>true</CheckUnique>
<Autonumbering>true</Autonumbering>
<DefaultPresentation>AsDescription</DefaultPresentation>
<EditType>InDialog</EditType>
<QuickChoice>{str(cat.quick_choice).lower()}</QuickChoice>
<ChoiceMode>BothWays</ChoiceMode>
<InputByString/><SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>
<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>
<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>
<DefaultObjectForm/><DefaultFolderForm/><DefaultListForm/><DefaultChoiceForm/>
<DefaultFolderChoiceForm/><AuxiliaryObjectForm/><AuxiliaryFolderForm/>
<AuxiliaryListForm/><AuxiliaryChoiceForm/><AuxiliaryFolderChoiceForm/>
<PredefinedDataUpdate>AutoUpdate</PredefinedDataUpdate>
<DataLockFields/><DataLockControlMode>Managed</DataLockControlMode>
<FullTextSearch>Use</FullTextSearch>
<ObjectPresentation></ObjectPresentation>
<ExtendedObjectPresentation/><ListPresentation/><ExtendedListPresentation/>
<Explanation/>
<CreateOnInput>Use</CreateOnInput>
<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
<DataHistory>DontUse</DataHistory>
<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>
<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>
{desc_syn}
</Properties>
<ChildObjects>{children}</ChildObjects>
</Catalog>
</MetaDataObject>
"""
    pres = (
        f"<ObjectPresentation>{_inner_syn(cat.object_presentation)}</ObjectPresentation>"
        if cat.object_presentation
        else "<ObjectPresentation/>"
    )
    body = body.replace(
        "<ObjectPresentation></ObjectPresentation>",
        pres,
    )
    _write(out / "Catalogs" / f"{cat.name}.xml", body)
    if cat.predefined:
        items = "".join(
            f"<Item><Name>{escape(p['name'])}</Name>"
            f"<Description>{escape(p.get('description', p['name']))}</Description>"
            "<Code/><IsFolder>false</IsFolder></Item>"
            for p in cat.predefined
        )
        p = out / "Catalogs" / cat.name / "Ext" / "Predefined.xml"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<PredefinedData {NSMAP}version="{FMT}">
{items}
</PredefinedData>
""",
            encoding="utf-8",
        )
    for form in cat.forms:
        _write_form_stub("Catalogs", cat.name, form, out)


def _inner_syn(text: str) -> str:
    return (
        "<v8:item><v8:lang>ru</v8:lang>"
        f"<v8:content>{escape(text)}</v8:content></v8:item>"
    )


def _write_enum(en, out: Path) -> None:
    cats = [("EnumRef", "Ref"), ("EnumManager", "Manager"), ("EnumList", "List")]
    values = "".join(
        f"""<EnumValue uuid="{uid('ev', en.name, v)}">
<Properties><Name>{escape(v)}</Name>{_syn(v)}<Comment/></Properties>
</EnumValue>"""
        for v in en.values
    )
    _write(
        out / "Enums" / f"{en.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Enum uuid="{uid('enum', en.name)}">
{_generated('Enum', en.name, cats)}
<Properties>
<Name>{escape(en.name)}</Name>
{_syn(en.name)}
<Comment/>
<UseStandardCommands>true</UseStandardCommands>
<StandardAttributes/>
<Characteristics/>
<QuickChoice>true</QuickChoice>
<ChoiceMode>BothWays</ChoiceMode>
<DefaultListForm/><DefaultChoiceForm/>
<AuxiliaryListForm/><AuxiliaryChoiceForm/>
<ListPresentation/><ExtendedListPresentation/><Explanation/>
<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
</Properties>
<ChildObjects>{values}</ChildObjects>
</Enum>
</MetaDataObject>
""",
    )


def _write_document(doc: Document, out: Path) -> None:
    cats = [
        ("DocumentObject", "Object"),
        ("DocumentRef", "Ref"),
        ("DocumentSelection", "Selection"),
        ("DocumentList", "List"),
        ("DocumentManager", "Manager"),
    ]
    children = "".join(_attr_xml(a) for a in doc.attributes)
    children += "".join(_ts_xml("Document", doc.name, ts) for ts in doc.tabular_sections)
    children += "".join(f"<Form>{escape(f.name)}</Form>" for f in doc.forms)
    regs = "".join(
        f'<xr:Item xsi:type="xr:MDObjectRef">AccumulationRegister.{escape(r)}</xr:Item>'
        for r, _ in doc.register_records
    )
    _write(
        out / "Documents" / f"{doc.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Document uuid="{uid('doc', doc.name)}">
{_generated('Document', doc.name, cats)}
<Properties>
<Name>{escape(doc.name)}</Name>
{_syn(doc.synonym or doc.name)}
<Comment/>
<UseStandardCommands>true</UseStandardCommands>
<Numerator/>
<NumberType>String</NumberType>
<NumberLength>9</NumberLength>
<NumberAllowedLength>Variable</NumberAllowedLength>
<RegisterRecordsDeletion>AutoDeleteOnUnpost</RegisterRecordsDeletion>
<SequenceFilling>AutoFill</SequenceFilling>
<RegisterRecordsWritingOnPost>WriteSelected</RegisterRecordsWritingOnPost>
<PostInPrivilegedMode>true</PostInPrivilegedMode>
<UnpostInPrivilegedMode>true</UnpostInPrivilegedMode>
<IncludeHelpInContents>false</IncludeHelpInContents>
<DataLockFields/><DataLockControlMode>Managed</DataLockControlMode>
<FullTextSearch>Use</FullTextSearch>
<ObjectPresentation/><ExtendedObjectPresentation/>
<ListPresentation/><ExtendedListPresentation/><Explanation/>
<ChoiceHistoryOnInput>Auto</ChoiceHistoryOnInput>
<DataHistory>DontUse</DataHistory>
<UpdateDataHistoryImmediatelyAfterWrite>false</UpdateDataHistoryImmediatelyAfterWrite>
<ExecuteAfterWriteDataHistoryVersionProcessing>false</ExecuteAfterWriteDataHistoryVersionProcessing>
<NumberPeriodicity>Nonperiodical</NumberPeriodicity>
<CheckUnique>true</CheckUnique>
<Autonumbering>true</Autonumbering>
<StandardAttributes/>
<Characteristics/>
<BasedOn/>
<InputByString/>
<CreateOnInput>Use</CreateOnInput>
<SearchStringModeOnInputByString>Begin</SearchStringModeOnInputByString>
<FullTextSearchOnInputByString>DontUse</FullTextSearchOnInputByString>
<ChoiceDataGetModeOnInputByString>Directly</ChoiceDataGetModeOnInputByString>
<DefaultObjectForm/><DefaultListForm/><DefaultChoiceForm/>
<AuxiliaryObjectForm/><AuxiliaryListForm/><AuxiliaryChoiceForm/>
<Posting>Allow</Posting>
<RealTimePosting>Allow</RealTimePosting>
<RegisterRecords>{regs}</RegisterRecords>
<PostInPrivilegedMode>true</PostInPrivilegedMode>
</Properties>
<ChildObjects>{children}</ChildObjects>
</Document>
</MetaDataObject>
""",
    )
    if doc.object_module.strip():
        p = out / "Documents" / doc.name / "Ext" / "ObjectModule.bsl"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\ufeff" + doc.object_module, encoding="utf-8")
    for form in doc.forms:
        if doc.form_module and not form.module:
            form.module = doc.form_module
        _write_form_stub("Documents", doc.name, form, out)


# в IR тип регистра называется как в методичке, в XML 1С ждёт значение перечисления
REGISTER_TYPE_XML = {"Balances": "Balance", "Balance": "Balance", "Turnovers": "Turnovers"}


def _reg_field_xml(field: Attribute, tag: str) -> str:
    """Измерение/ресурс регистра — свой минимальный набор свойств.

    Раньше сюда подставлялся XML обычного реквизита: у него есть свойства,
    которых у измерения быть не может (FillFromFillingValue, CreateOnInput,
    DataHistory и прочие), и конфигуратор на таком падал с access violation,
    даже не сообщая, что именно ему не нравится.
    """
    return f"""<{tag} uuid="{uid(tag.lower(), field.name)}">
<Properties>
<Name>{escape(field.name)}</Name>
{_syn(field.synonym or field.name)}
<Comment/>
<Type>{_type_xml(field.type)}</Type>
{"<Indexing>DontIndex</Indexing>" if tag == "Dimension" else ""}
<FullTextSearch>Use</FullTextSearch>
</Properties>
</{tag}>"""


def _write_register(reg: Register, out: Path) -> None:
    cats = [
        ("AccumulationRegisterRecord", "Record"),
        ("AccumulationRegisterManager", "Manager"),
        ("AccumulationRegisterSelection", "Selection"),
        ("AccumulationRegisterList", "List"),
        ("AccumulationRegisterRecordSet", "RecordSet"),
        ("AccumulationRegisterRecordKey", "RecordKey"),
    ]
    dims = "".join(_reg_field_xml(d, "Dimension") for d in reg.dimensions)
    resources = "".join(_reg_field_xml(r, "Resource") for r in reg.resources)
    children = dims + resources + "".join(f"<Form>{escape(f.name)}</Form>" for f in reg.forms)
    _write(
        out / "AccumulationRegisters" / f"{reg.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<AccumulationRegister uuid="{uid('reg', reg.name)}">
{_generated('AccumulationRegister', reg.name, cats)}
<Properties>
<Name>{escape(reg.name)}</Name>
{_syn(reg.name)}
<Comment/>
<UseStandardCommands>true</UseStandardCommands>
<RegisterType>{REGISTER_TYPE_XML.get(reg.register_type, reg.register_type)}</RegisterType>
</Properties>
<ChildObjects>{children}</ChildObjects>
</AccumulationRegister>
</MetaDataObject>
""",
    )
    for form in reg.forms:
        _write_form_stub("AccumulationRegisters", reg.name, form, out)


def _write_report(rep, out: Path) -> None:
    cats = [("ReportObject", "Object"), ("ReportManager", "Manager")]
    children = "<Template>ОсновнаяСхемаКомпоновкиДанных</Template>"
    children += "".join(f"<Form>{escape(f.name)}</Form>" for f in rep.forms)
    _write(
        out / "Reports" / f"{rep.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Report uuid="{uid('rep', rep.name)}">
{_generated('Report', rep.name, cats)}
<Properties>
<Name>{escape(rep.name)}</Name>
{_syn(rep.name)}
<Comment/>
<UseStandardCommands>true</UseStandardCommands>
<DefaultForm/>
<AuxiliaryForm/>
<MainDataCompositionSchema>Report.{escape(rep.name)}.Template.ОсновнаяСхемаКомпоновкиДанных</MainDataCompositionSchema>
<DefaultSettingsForm/><AuxiliarySettingsForm/><DefaultVariantForm/>
<VariantsStorage/><SettingsStorage/>
<IncludeHelpInContents>false</IncludeHelpInContents>
<ExtendedPresentation/><Explanation/>
</Properties>
<ChildObjects>{children}</ChildObjects>
</Report>
</MetaDataObject>
""",
    )
    fields = " ".join(rep.fields or ["Поле"])
    tpl = out / "Reports" / rep.name / "Templates" / "ОсновнаяСхемаКомпоновкиДанных" / "Ext" / "Template.xml"
    tpl.parent.mkdir(parents=True, exist_ok=True)
    tpl.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<DataCompositionSchema xmlns="http://v8.1c.ru/8.1/data-composition-system/schema" xmlns:dcscom="http://v8.1c.ru/8.1/data-composition-system/common" xmlns:dcscor="http://v8.1c.ru/8.1/data-composition-system/core" xmlns:dcsset="http://v8.1c.ru/8.1/data-composition-system/settings" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:v8ui="http://v8.1c.ru/8.1/data/ui" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dataSource>
<name>ИсточникДанных1</name>
<dataSourceType>Local</dataSourceType>
</dataSource>
<dataSet xsi:type="DataSetQuery">
<name>НаборДанных1</name>
<dataSource>ИсточникДанных1</dataSource>
<query>ВЫБРАТЬ {escape(fields)}
ИЗ {escape(rep.query_table or "ФинансовыеОперации.ОстаткиИОбороты")}
</query>
</dataSet>
</DataCompositionSchema>
""",
        encoding="utf-8",
    )
    _write(
        out / "Reports" / rep.name / "Templates" / "ОсновнаяСхемаКомпоновкиДанных.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Template uuid="{uid('tpl', rep.name)}">
<Properties>
<Name>ОсновнаяСхемаКомпоновкиДанных</Name>
{_syn("Основная схема компоновки данных")}
<Comment/>
<TemplateType>DataCompositionSchema</TemplateType>
</Properties>
</Template>
</MetaDataObject>
""",
    )
    for form in rep.forms:
        _write_form_stub("Reports", rep.name, form, out)


# у формы объекта должен быть основной реквизит «Объект», иначе модуль формы,
# который к нему обращается, не проходит синтаксический контроль
MAIN_ATTR_TYPE = {
    "Catalogs": "CatalogObject",
    "Documents": "DocumentObject",
}


def _form_attributes(folder: str, owner: str, form) -> str:
    kind = MAIN_ATTR_TYPE.get(folder)
    if kind is None or getattr(form, "kind", "object") != "object":
        return "<Attributes/>"
    return (
        '<Attributes><Attribute name="Объект" id="1">'
        f"<Type><v8:Type>cfg:{kind}.{escape(owner)}</v8:Type></Type>"
        "<MainAttribute>true</MainAttribute>"
        "<SavedData>true</SavedData>"
        "</Attribute></Attributes>"
    )


def _write_form_stub(folder: str, owner: str, form, out: Path) -> None:
    _write(
        out / folder / owner / "Forms" / f"{form.name}.xml",
        f"""<MetaDataObject {NSMAP}version="{FMT}">
<Form uuid="{uid('form', owner, form.name)}">
<Properties>
<Name>{escape(form.name)}</Name>
{_syn(form.name)}
<Comment/>
<FormType>Managed</FormType>
<IncludeHelpInContents>false</IncludeHelpInContents>
<UsePurposes><v8:Value xsi:type="app:ApplicationUsePurpose">PlatformApplication</v8:Value></UsePurposes>
<UseStandardCommands>true</UseStandardCommands>
</Properties>
</Form>
</MetaDataObject>
""",
    )
    form_dir = out / folder / owner / "Forms" / form.name / "Ext"
    form_dir.mkdir(parents=True, exist_ok=True)
    (form_dir / "Form.xml").write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Form xmlns="http://v8.1c.ru/8.3/xcf/logform" xmlns:cfg="http://v8.1c.ru/8.1/data/enterprise/current-config" xmlns:v8="http://v8.1c.ru/8.1/data/core" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="{FMT}">
<AutoCommandBar name="ФормаКоманднаяПанель" id="-1"/>
<ChildItems/>
{_form_attributes(folder, owner, form)}
</Form>
""",
        encoding="utf-8",
    )
    if form.module.strip():
        mdir = form_dir / "Form"
        mdir.mkdir(exist_ok=True)
        (mdir / "Module.bsl").write_text("\ufeff" + form.module, encoding="utf-8")


def _write_dump_info(cfg: ConfigIR, out: Path) -> None:
    def meta(name: str, ident: str) -> str:
        ver = hashlib.md5(name.encode("utf-8")).hexdigest() + "00000000"
        return f'<Metadata name="{escape(name)}" id="{ident}" configVersion="{ver}"/>'

    chunks = [
        meta("Configuration." + cfg.name, uid("configuration", cfg.name)),
        meta("Language.Русский", uid("lang", "ru")),
        meta("Role.ПолныеПрава", uid("role", "ПолныеПрава")),
        meta(f"CommonModule.{SEED_MODULE}", uid("commonmodule", SEED_MODULE)),
    ]
    for n in cfg.subsystems:
        chunks.append(meta(f"Subsystem.{n}", uid("sub", n)))
    for n in cfg.catalogs:
        chunks.append(meta(f"Catalog.{n}", uid("cat", n)))
    for n in cfg.documents:
        chunks.append(meta(f"Document.{n}", uid("doc", n)))
    for n in cfg.enums:
        chunks.append(meta(f"Enum.{n}", uid("enum", n)))
    for n in cfg.registers:
        chunks.append(meta(f"AccumulationRegister.{n}", uid("reg", n)))
    for n in cfg.reports:
        chunks.append(meta(f"Report.{n}", uid("rep", n)))
    _write(
        out / "ConfigDumpInfo.xml",
        f"""<ConfigDumpInfo xmlns="http://v8.1c.ru/8.3/xcf/dumpinfo" xmlns:xen="http://v8.1c.ru/8.3/xcf/enums" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" format="Hierarchical" version="{FMT}">
<ConfigVersions>
{''.join(chunks)}
</ConfigVersions>
</ConfigDumpInfo>
""",
    )


def _write_ib_seed(world: World, out: Path) -> None:
    """JSON seed of enterprise-mode data for COM filler after XML load."""
    import json

    payload = {
        "items": [
            {
                "catalog": x.catalog,
                "description": x.description,
                "is_folder": x.is_folder,
                "parent": x.parent,
                "attrs": x.attrs,
                "tabular": x.tabular,
            }
            for x in world.ib.items
        ],
        "documents": [
            {
                "document": d.document,
                "number": d.number,
                "posted": d.posted,
                "attrs": d.attrs,
                "tabular": d.tabular,
            }
            for d in world.ib.documents
        ],
    }
    (out / "ib_seed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
