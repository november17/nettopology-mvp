#!/usr/bin/env python3
import sys, json, ipaddress, uuid
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QPen, QColor, QPainter, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QDockWidget,
    QWidget, QFormLayout, QLineEdit, QComboBox, QSpinBox, QPushButton, QVBoxLayout,
    QHBoxLayout, QListWidget, QListWidgetItem, QTabWidget, QTextEdit, QLabel,
    QMessageBox, QFileDialog, QGroupBox
)

APP_NAME = "NetTopology MVP"

@dataclass
class Port:
    id: str
    name: str
    mac: str = ""
    media: str = "ethernet"
    enabled: bool = True

@dataclass
class Bridge:
    name: str
    ports: List[str] = field(default_factory=list)

@dataclass
class Device:
    id: str
    name: str
    kind: str = "host"
    os: str = "Ubuntu Linux"
    x: float = 100
    y: float = 100
    ports: List[Port] = field(default_factory=list)
    bridges: List[Bridge] = field(default_factory=list)
    notes: str = ""

@dataclass
class Link:
    id: str
    a_device: str
    a_port: str
    b_device: str
    b_port: str
    network_id: str = ""

@dataclass
class Network:
    id: str
    name: str
    kind: str = "LAN"
    cidr: str = "192.168.10.0/24"
    vlan: int = 0
    gateway: str = ""
    ssid: str = ""
    security: str = "WPA2/WPA3"

class Topology:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.links: Dict[str, Link] = {}
        self.networks: Dict[str, Network] = {}

    def to_dict(self):
        return {
            "devices": [asdict(d) for d in self.devices.values()],
            "links": [asdict(x) for x in self.links.values()],
            "networks": [asdict(n) for n in self.networks.values()],
        }

    @staticmethod
    def from_dict(data):
        t = Topology()
        for d in data.get("devices", []):
            d["ports"] = [Port(**p) for p in d.get("ports", [])]
            d["bridges"] = [Bridge(**b) for b in d.get("bridges", [])]
            t.devices[d["id"]] = Device(**d)
        for x in data.get("links", []):
            t.links[x["id"]] = Link(**x)
        for n in data.get("networks", []):
            t.networks[n["id"]] = Network(**n)
        return t

class PortItem(QGraphicsEllipseItem):
    def __init__(self, scene, device_id, port_id, x, y):
        super().__init__(-7, -7, 14, 14)
        self.scene_ref = scene
        self.device_id = device_id
        self.port_id = port_id
        self.setPos(x, y)
        self.setBrush(QBrush(QColor("#38bdf8")))
        self.setPen(QPen(QColor("#0f172a"), 1))
        self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setToolTip("Port: " + port_id + "\nDrag from this port to another port")

    def mousePressEvent(self, event):
        self.scene_ref.port_clicked(self)
        super().mousePressEvent(event)

class DeviceItem(QGraphicsRectItem):
    def __init__(self, scene, device: Device):
        super().__init__(0, 0, 170, 92)
        self.scene_ref = scene
        self.device_id = device.id
        self.setPos(device.x, device.y)
        self.setBrush(QBrush(QColor("#172033")))
        self.setPen(QPen(QColor("#64748b"), 2))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.text = QGraphicsTextItem(self)
        self.text.setDefaultTextColor(QColor("#f8fafc"))
        self.refresh()

    def refresh(self):
        d = self.scene_ref.topology.devices[self.device_id]
        self.text.setPlainText(f"{d.name}\n{d.kind} • {d.os}\n{len(d.ports)} ports")
        self.text.setPos(10, 8)

    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            d = self.scene_ref.topology.devices[self.device_id]
            d.x, d.y = value.x(), value.y()
            self.scene_ref.rebuild_links()
        return super().itemChange(change, value)

class LinkItem(QGraphicsLineItem):
    def __init__(self, scene, link: Link):
        super().__init__()
        self.scene_ref = scene
        self.link_id = link.id
        self.setPen(QPen(QColor("#94a3b8"), 3))
        self.setZValue(-1)
        self.refresh()

    def refresh(self):
        l = self.scene_ref.topology.links[self.link_id]
        a = self.scene_ref.port_scene_pos(l.a_device, l.a_port)
        b = self.scene_ref.port_scene_pos(l.b_device, l.b_port)
        if a and b:
            self.setLine(a.x(), a.y(), b.x(), b.y())
        n = self.scene_ref.topology.networks.get(l.network_id)
        self.setToolTip(f"{n.name if n else 'Unassigned'} | {l.a_port} ↔ {l.b_port}")

class TopologyScene(QGraphicsScene):
    def __init__(self, topology, parent=None):
        super().__init__(parent)
        self.topology = topology
        self.window = parent
        self.port_selection = None
        self.device_items = {}
        self.port_items = {}
        self.link_items = {}
        self.render_all()

    def render_all(self):
        self.clear()
        self.device_items.clear(); self.port_items.clear(); self.link_items.clear()
        for d in self.topology.devices.values():
            item = DeviceItem(self, d); self.addItem(item); self.device_items[d.id] = item
            self._add_ports(d)
        for l in self.topology.links.values():
            item = LinkItem(self, l); self.addItem(item); self.link_items[l.id] = item
        self.setSceneRect(-500, -500, 3000, 2000)

    def _add_ports(self, d):
        base_x = d.x + 170
        for i, p in enumerate(d.ports):
            y = d.y + 22 + i * 16
            pi = PortItem(self, d.id, p.id, base_x, y)
            self.addItem(pi); self.port_items[(d.id,p.id)] = pi
            label = QGraphicsTextItem(p.name)
            label.setDefaultTextColor(QColor("#cbd5e1")); label.setScale(0.7)
            label.setPos(base_x + 10, y - 8); self.addItem(label)

    def port_scene_pos(self, device_id, port_id):
        p = self.port_items.get((device_id, port_id))
        return p.scenePos() if p else None

    def port_clicked(self, item):
        if self.port_selection is None:
            self.port_selection = item
            item.setBrush(QBrush(QColor("#f59e0b")))
        else:
            first = self.port_selection
            first.setBrush(QBrush(QColor("#38bdf8")))
            if (first.device_id, first.port_id) != (item.device_id, item.port_id):
                self.window.create_link(first.device_id, first.port_id, item.device_id, item.port_id)
            self.port_selection = None

    def rebuild_links(self):
        for x in self.link_items.values(): x.refresh()

class ConfigEngine:
    @staticmethod
    def allocate_ips(topology):
        assignments = []
        for n in topology.networks.values():
            try:
                net = ipaddress.ip_network(n.cidr, strict=False)
                hosts = list(net.hosts())
            except Exception:
                continue
            # deterministic assignment: gateways first, then devices attached to links on the network
            used = set()
            if n.gateway:
                try: used.add(ipaddress.ip_address(n.gateway))
                except Exception: pass
            idx = 0
            for l in topology.links.values():
                if l.network_id != n.id: continue
                for did in [l.a_device, l.b_device]:
                    if idx >= len(hosts): break
                    ip = str(hosts[idx])
                    assignments.append((n.name, did, ip, n.cidr))
                    idx += 1
        return assignments

    @staticmethod
    def generate(topology):
        lines = ["# NetTopology MVP generated configuration plan", "# Review and adapt before applying to production.", ""]
        lines += ["## Network addressing"]
        for n in topology.networks.values():
            lines.append(f"- {n.name}: {n.kind} {n.cidr}" + (f" VLAN {n.vlan}" if n.vlan else ""))
            if n.gateway: lines.append(f"  gateway: {n.gateway}")
            if n.ssid: lines.append(f"  SSID: {n.ssid} security: {n.security}")
        lines += ["", "## Suggested device configuration"]
        assignments = ConfigEngine.allocate_ips(topology)
        for d in topology.devices.values():
            lines += [f"", f"### {d.name} ({d.os})"]
            ds = [a for a in assignments if a[1] == d.id]
            if not ds:
                lines.append("No IP assignment derived yet.")
            if "Ubuntu" in d.os or "Debian" in d.os or "Linux" in d.os:
                for net, _, ip, cidr in ds:
                    lines.append(f"ip address add {ip}/{ipaddress.ip_network(cidr, strict=False).prefixlen} dev <interface-for-{net}>")
                if d.kind == "router":
                    lines.append("sysctl -w net.ipv4.ip_forward=1")
                    lines.append("# Add routes based on connected networks and policy below")
            elif "Cisco" in d.os:
                for net, _, ip, cidr in ds:
                    lines.append(f"interface <interface-for-{net}>")
                    lines.append(f" ip address {ip} {ipaddress.ip_network(cidr, strict=False).netmask}")
                    lines.append(" no shutdown")
                if d.kind == "router": lines.append("ip routing")
            else:
                lines.append("OS-specific generator not yet implemented; topology facts are still available.")
        lines += ["", "## Routing plan"]
        for d in topology.devices.values():
            if d.kind != "router": continue
            attached = set()
            for l in topology.links.values():
                if l.a_device == d.id or l.b_device == d.id:
                    if l.network_id: attached.add(l.network_id)
            lines.append(f"### {d.name}")
            for nid in attached:
                n = topology.networks.get(nid)
                if n:
                    lines.append(f"connected route: {n.cidr} via connected interface")
            lines.append("Add static routes only for remote networks not directly connected.")
        lines += ["", "## Firewall plan"]
        lines.append("Default policy recommendation: deny unsolicited inbound traffic between security zones; explicitly allow required services.")
        for n in topology.networks.values():
            if n.kind in ("WAN", "WiFi", "Guest"):
                lines.append(f"- Zone {n.name}: treat as untrusted unless explicitly marked trusted.")
        lines += ["", "## Validation warnings"]
        # Basic validation
        for l in topology.links.values():
            if not l.network_id:
                lines.append(f"WARNING: link {l.id} has no LAN/VLAN/network assigned.")
        for d in topology.devices.values():
            if d.kind == "router" and not d.ports:
                lines.append(f"WARNING: router {d.name} has no ports.")
            for p in d.ports:
                if not p.mac:
                    lines.append(f"WARNING: {d.name} port {p.name} has no MAC address.")
        return "\n".join(lines)

class Inspector(QWidget):
    def __init__(self, window):
        super().__init__(); self.window = window
        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget(); self.layout.addWidget(self.tabs)
        self.device_tab = QWidget(); self.net_tab = QWidget(); self.config_tab = QWidget()
        self.tabs.addTab(self.device_tab, "Device"); self.tabs.addTab(self.net_tab, "Networks"); self.tabs.addTab(self.config_tab, "Config")
        self._device_ui(); self._net_ui(); self._config_ui()

    def _device_ui(self):
        l = QVBoxLayout(self.device_tab)
        form = QFormLayout(); self.dname=QLineEdit(); self.kind=QComboBox(); self.kind.addItems(["host","router","switch","firewall","access point","server"])
        self.os=QComboBox(); self.os.addItems(["Ubuntu Linux","Debian Linux","OpenWrt","Cisco IOS","MikroTik RouterOS","Windows","Other"])
        self.notes=QLineEdit(); self.ports=QSpinBox(); self.ports.setRange(0,128); self.ports.setValue(4)
        form.addRow("Name",self.dname); form.addRow("Type",self.kind); form.addRow("OS",self.os); form.addRow("Ports",self.ports); form.addRow("Notes",self.notes); l.addLayout(form)
        b=QPushButton("Add device"); b.clicked.connect(self.window.add_device); l.addWidget(b)
        self.device_list=QListWidget(); self.device_list.itemClicked.connect(self.window.select_device); l.addWidget(self.device_list)
        self.port_edit=QTextEdit(); self.port_edit.setPlaceholderText("Port list appears here. Format: port name | MAC | media"); l.addWidget(self.port_edit)
        pb=QPushButton("Apply port/MAC edits"); pb.clicked.connect(self.window.apply_ports); l.addWidget(pb)

    def _net_ui(self):
        l=QVBoxLayout(self.net_tab); form=QFormLayout(); self.nname=QLineEdit(); self.nkind=QComboBox(); self.nkind.addItems(["LAN","VLAN","WAN","WiFi","Guest"]); self.cidr=QLineEdit("192.168.10.0/24"); self.vlan=QSpinBox(); self.vlan.setRange(0,4094); self.vlan.setValue(0); self.gateway=QLineEdit(); self.ssid=QLineEdit(); self.security=QComboBox(); self.security.addItems(["WPA2/WPA3","WPA3","Open"])
        for a,b in [("Name",self.nname),("Type",self.nkind),("CIDR",self.cidr),("VLAN ID",self.vlan),("Gateway",self.gateway),("SSID",self.ssid),("WiFi security",self.security)]: form.addRow(a,b)
        l.addLayout(form); b=QPushButton("Add network"); b.clicked.connect(self.window.add_network); l.addWidget(b); self.net_list=QListWidget(); self.net_list.itemClicked.connect(self.window.select_network); l.addWidget(self.net_list)
        b=QPushButton("Assign selected network to selected link"); b.clicked.connect(self.window.assign_network); l.addWidget(b)

    def _config_ui(self):
        l=QVBoxLayout(self.config_tab); self.config=QTextEdit(); self.config.setReadOnly(True); l.addWidget(self.config); b=QPushButton("Generate / refresh plan"); b.clicked.connect(self.window.refresh_config); l.addWidget(b)

    def refresh_devices(self, topology):
        self.device_list.clear()
        for d in topology.devices.values(): self.device_list.addItem(QListWidgetItem(f"{d.name}  [{d.kind}]"))

    def refresh_networks(self, topology):
        self.net_list.clear()
        for n in topology.networks.values(): self.net_list.addItem(QListWidgetItem(f"{n.name}  [{n.kind} {n.cidr}]") )

    def load_device(self, d):
        self.dname.setText(d.name); self.kind.setCurrentText(d.kind); self.os.setCurrentText(d.os); self.ports.setValue(len(d.ports)); self.notes.setText(d.notes)
        self.port_edit.setPlainText("\n".join(f"{p.name} | {p.mac} | {p.media}" for p in d.ports))

    def load_network(self,n):
        self.nname.setText(n.name); self.nkind.setCurrentText(n.kind); self.cidr.setText(n.cidr); self.vlan.setValue(n.vlan); self.gateway.setText(n.gateway); self.ssid.setText(n.ssid); self.security.setCurrentText(n.security)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(APP_NAME); self.resize(1400,850); self.topology=Topology(); self.selected_device=None; self.selected_network=None; self.selected_link=None
        self.scene=TopologyScene(self.topology,self); self.view=QGraphicsView(self.scene); self.view.setRenderHint(QPainter.RenderHint.Antialiasing); self.setCentralWidget(self.view)
        self.inspector=Inspector(self); dock=QDockWidget("Network Inspector",self); dock.setWidget(self.inspector); dock.setMinimumWidth(390); self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,dock)
        self._menu(); self.refresh()

    def _menu(self):
        bar=self.menuBar(); f=bar.addMenu("File")
        for name, fn in [("New",self.new_project),("Open",self.open_project),("Save",self.save_project),("Export config plan",self.export_config)]:
            a=QAction(name,self); a.triggered.connect(fn); f.addAction(a)
        a=QAction("Delete selected device",self); a.triggered.connect(self.delete_device); bar.addAction(a)

    def refresh(self):
        self.scene.render_all(); self.inspector.refresh_devices(self.topology); self.inspector.refresh_networks(self.topology); self.refresh_config()

    def add_device(self):
        name=self.inspector.dname.text().strip() or f"Device {len(self.topology.devices)+1}"; count=self.inspector.ports.value(); did=str(uuid.uuid4())
        ports=[Port(str(uuid.uuid4()),f"eth{i}") for i in range(count)]
        d=Device(did,name,self.inspector.kind.currentText(),self.inspector.os.currentText(),100+len(self.topology.devices)*210,100+(len(self.topology.devices)%3)*150,ports,[],self.inspector.notes.text())
        self.topology.devices[did]=d; self.selected_device=did; self.refresh()

    def select_device(self,item):
        idx=self.inspector.device_list.row(item); ds=list(self.topology.devices.values());
        if idx < len(ds): self.selected_device=ds[idx]; self.inspector.load_device(ds[idx])

    def apply_ports(self):
        if not self.selected_device or not isinstance(self.selected_device,Device): return
        lines=self.inspector.port_edit.toPlainText().splitlines(); ports=[]
        for i,line in enumerate(lines):
            parts=[x.strip() for x in line.split("|")];
            if not parts or not parts[0]: continue
            ports.append(Port(str(uuid.uuid4()),parts[0],parts[1] if len(parts)>1 else "",parts[2] if len(parts)>2 else "ethernet"))
        self.selected_device.ports=ports; self.refresh()

    def create_link(self,a_dev,a_port,b_dev,b_port):
        lid=str(uuid.uuid4()); self.topology.links[lid]=Link(lid,a_dev,a_port,b_dev,b_port); self.selected_link=lid; self.refresh()

    def add_network(self):
        n=Network(str(uuid.uuid4()),self.inspector.nname.text().strip() or f"LAN {len(self.topology.networks)+1}",self.inspector.nkind.currentText(),self.inspector.cidr.text().strip(),self.inspector.vlan.value(),self.inspector.gateway.text().strip(),self.inspector.ssid.text().strip(),self.inspector.security.currentText())
        self.topology.networks[n.id]=n; self.selected_network=n.id; self.refresh()

    def select_network(self,item):
        idx=self.inspector.net_list.row(item); ns=list(self.topology.networks.values());
        if idx < len(ns): self.selected_network=ns[idx].id; self.inspector.load_network(ns[idx])

    def assign_network(self):
        if self.selected_link and self.selected_network:
            self.topology.links[self.selected_link].network_id=self.selected_network; self.refresh()
        else: QMessageBox.information(self,"Select a link","Click a link after creating it, then choose a network.")

    def refresh_config(self): self.inspector.config.setPlainText(ConfigEngine.generate(self.topology))

    def delete_device(self):
        if not isinstance(self.selected_device,Device): return
        did=self.selected_device.id; self.topology.devices.pop(did,None)
        for lid,l in list(self.topology.links.items()):
            if l.a_device==did or l.b_device==did: self.topology.links.pop(lid)
        self.selected_device=None; self.refresh()

    def new_project(self): self.topology=Topology(); self.scene.topology=self.topology; self.refresh()

    def save_project(self):
        path,_=QFileDialog.getSaveFileName(self,"Save NetTopology project","network.json","NetTopology (*.json)")
        if path:
            with open(path,"w",encoding="utf-8") as f: json.dump(self.topology.to_dict(),f,indent=2)

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,"Open NetTopology project","","NetTopology (*.json)")
        if path:
            with open(path,encoding="utf-8") as f: self.topology=Topology.from_dict(json.load(f))
            self.scene.topology=self.topology; self.refresh()

    def export_config(self):
        path,_=QFileDialog.getSaveFileName(self,"Export configuration plan","network-config.txt","Text (*.txt)")
        if path:
            with open(path,"w",encoding="utf-8") as f: f.write(ConfigEngine.generate(self.topology))

if __name__ == "__main__":
    app=QApplication(sys.argv); app.setApplicationName(APP_NAME); w=MainWindow(); w.show(); sys.exit(app.exec())
