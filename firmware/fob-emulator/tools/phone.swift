// A Mac standing in for the phone (IREM-8): listens for iphone-remote presses and acks each
// one exactly as protocol.md §3–§4 says (and as ScreenEye's KeyFob.swift does), so the fob
// emulator's round trip can be tested without an iPhone. macOS isn't iOS: its scan and
// advertising timing differ, so latency figures from here say nothing about §7.3–§7.4.
//
//   swift firmware/fob-emulator/tools/phone.swift          # ack presses
//   swift firmware/fob-emulator/tools/phone.swift --hold   # hold one ack on air, for the
//                                                          # emulator's monitor (m) to time
//
// The terminal app running it needs Bluetooth permission (System Settings → Privacy &
// Security → Bluetooth).
import CoreBluetooth
import Foundation

let pressUUID = CBUUID(string: "3B89DBAA-2669-4548-9D04-6876798D0903")
let ackPrefix: [UInt8] = [0x6F, 0xDA, 0xD3, 0x56, 0x81, 0x65, 0x4F, 0xDB, 0xA4, 0xF2, 0xB2, 0x5C, 0x2B]
let ackDuration = 0.150
let hold = CommandLine.arguments.contains("--hold")

struct Press: Hashable { let fobID: UInt8; let counter: UInt16; let battery: UInt8 }

func decode(_ data: Data) -> Press? {
    let b = [UInt8](data)
    guard b.count >= 7, b[0] == 0xFF, b[1] == 0xFF, b[2] == 0x01, b[3] <= 7 else { return nil }
    return Press(fobID: b[3], counter: UInt16(b[4]) | UInt16(b[5]) << 8, battery: b[6])
}

func ackUUID(_ p: Press) -> CBUUID {
    let b = ackPrefix + [p.fobID, UInt8(p.counter >> 8), UInt8(p.counter & 0xFF)]
    return CBUUID(data: Data(b))
}

final class Phone: NSObject, CBCentralManagerDelegate, CBPeripheralManagerDelegate {
    var central: CBCentralManager!
    var peripheral: CBPeripheralManager!
    var last: [UInt8: (counter: UInt16, seen: Date)] = [:]
    var queue: [CBUUID] = []
    var current: CBUUID?
    var start = Date()

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main)
        peripheral = CBPeripheralManager(delegate: self, queue: .main)
    }

    func t() -> String { String(format: "%8.3f", Date().timeIntervalSince(start)) }

    func centralManagerDidUpdateState(_ c: CBCentralManager) {
        print("\(t()) central: \(c.state.rawValue) (5 = on, 3 = unauthorised)")
        if c.state == .poweredOn {
            c.scanForPeripherals(withServices: [pressUUID],
                                 options: [CBCentralManagerScanOptionAllowDuplicatesKey: true])
        }
    }

    func peripheralManagerDidUpdateState(_ p: CBPeripheralManager) {
        print("\(t()) peripheral: \(p.state.rawValue)")
        if hold, p.state == .poweredOn {
            let ack = ackUUID(Press(fobID: 7, counter: 0xFFFF, battery: 0))
            p.startAdvertising([CBAdvertisementDataServiceUUIDsKey: [ack]])
            print("\(t()) holding \(ack.uuidString) on air")
            return
        }
        next()
    }

    func centralManager(_ c: CBCentralManager, didDiscover _: CBPeripheral,
                        advertisementData ad: [String: Any], rssi: NSNumber) {
        guard !hold, let data = ad[CBAdvertisementDataManufacturerDataKey] as? Data,
              let press = decode(data) else { return }
        let now = Date()
        let prev = last[press.fobID]
        last[press.fobID] = (press.counter, now)
        let ack = ackUUID(press)
        if ack != current, !queue.contains(ack) {
            queue.append(ack)
            if current == nil { next() }
        }
        if prev == nil || prev!.counter != press.counter || now.timeIntervalSince(prev!.seen) > 5 {
            print("\(t()) press: fob \(press.fobID) #\(press.counter), \(Double(press.battery) * 0.02) V, RSSI \(rssi)")
        }
    }

    func next() {
        guard current == nil, peripheral.state == .poweredOn, !queue.isEmpty else { return }
        let ack = queue.removeFirst()
        current = ack
        peripheral.startAdvertising([CBAdvertisementDataServiceUUIDsKey: [ack]])
        print("\(t()) ack:   \(ack.uuidString)")
        DispatchQueue.main.asyncAfter(deadline: .now() + ackDuration) {
            self.peripheral.stopAdvertising()
            self.current = nil
            self.next()
        }
    }

    func peripheralManagerDidStartAdvertising(_ p: CBPeripheralManager, error: Error?) {
        if let error { print("\(t()) ack advert failed: \(error.localizedDescription)") }
    }
}

setvbuf(stdout, nil, _IOLBF, 0)
let phone = Phone()
RunLoop.main.run()
