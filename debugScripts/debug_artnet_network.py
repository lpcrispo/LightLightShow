"""Diagnostic complet du réseau Art-Net"""
import socket
import struct
import time
import numpy as np

def test_network_connectivity():
    """Test de connectivité réseau basique"""
    print("=== NETWORK CONNECTIVITY TEST ===")
    
    target_ip = "192.168.18.28"
    
    # Test ping (Windows)
    import subprocess
    try:
        result = subprocess.run(['ping', '-n', '1', target_ip], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✓ {target_ip} is reachable")
        else:
            print(f"✗ {target_ip} is NOT reachable")
            print(f"Ping output: {result.stdout}")
    except Exception as e:
        print(f"✗ Ping test failed: {e}")

def test_socket_creation():
    """Test de création et configuration du socket"""
    print("\n=== SOCKET CREATION TEST ===")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        print("✓ UDP socket created successfully")
        print("✓ Broadcast enabled")
        
        # Test de binding (optionnel pour l'envoi)
        try:
            sock.bind(('0.0.0.0', 0))  # Bind à un port automatique
            local_addr = sock.getsockname()
            print(f"✓ Socket bound to {local_addr}")
        except Exception as e:
            print(f"⚠ Socket bind test: {e}")
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"✗ Socket creation failed: {e}")
        return False

def test_artnet_packet_construction():
    """Test de construction du paquet Art-Net"""
    print("\n=== ART-NET PACKET CONSTRUCTION TEST ===")
    
    try:
        # Construire un paquet Art-Net manuellement
        header = b"Art-Net\x00"
        opcode = struct.pack('<H', 0x5000)  # OpDmx
        protocol = struct.pack('>H', 14)    # Version 14
        sequence = b'\x00'
        physical = b'\x00'
        universe = struct.pack('<H', 0)     # Univers 0
        length = struct.pack('>H', 512)     # 512 canaux
        
        # Données DMX test - Rouge sur les 4 premiers canaux
        dmx_data = bytearray(512)
        dmx_data[0] = 255  # Canal 1 - Rouge
        dmx_data[4] = 255  # Canal 5 - Rouge
        dmx_data[8] = 255  # Canal 9 - Rouge
        
        # Assembler le paquet
        packet = header + opcode + protocol + sequence + physical + universe + length + dmx_data
        
        print(f"✓ Art-Net packet constructed: {len(packet)} bytes")
        print(f"  Header: {header}")
        print(f"  OpCode: 0x5000 (DMX)")
        print(f"  Universe: 0")
        print(f"  Data length: 512")
        print(f"  Active channels: 1, 5, 9 = 255")
        
        return packet
        
    except Exception as e:
        print(f"✗ Packet construction failed: {e}")
        return None

def test_raw_send(packet):
    """Test d'envoi brut via socket"""
    print("\n=== RAW SOCKET SEND TEST ===")
    
    if not packet:
        print("✗ No packet to send")
        return False
    
    target_ip = "192.168.18.28"
    target_port = 6454
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Envoyer plusieurs paquets
        for i in range(3):
            bytes_sent = sock.sendto(packet, (target_ip, target_port))
            print(f"✓ Sent packet {i+1}: {bytes_sent} bytes to {target_ip}:{target_port}")
            time.sleep(0.5)
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"✗ Raw send failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_application_artnet():
    """Test du système Art-Net de l'application"""
    print("\n=== APPLICATION ART-NET TEST ===")
    
    try:
        from config.artnet_config import ArtNetConfig
        from artnet.art_net_client import ArtNetClient
        
        config = ArtNetConfig(ip="192.168.18.28", universe=0)
        print(f"✓ Config created: {config.ip}:{config.universe}")
        
        client = ArtNetClient(config)
        print(f"✓ Client created, target: {client.target_ip}")
        
        # Test d'envoi avec données réelles
        test_data = np.zeros(512, dtype=np.uint8)
        test_data[0] = 255   # Canal 1
        test_data[4] = 128   # Canal 5
        test_data[8] = 64    # Canal 9
        
        print("Sending test data...")
        for i in range(3):
            result = client.send_dmx(0, test_data)
            print(f"  Send attempt {i+1}: {'SUCCESS' if result else 'FAILED'}")
            time.sleep(0.5)
        
        client.close()
        return True
        
    except Exception as e:
        print(f"✗ Application test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_firewall():
    """Vérifications relatives au firewall"""
    print("\n=== FIREWALL CHECK ===")
    
    print("⚠ Manual checks required:")
    print("  1. Windows Firewall might be blocking UDP traffic")
    print("  2. Check if port 6454 is open outbound")
    print("  3. Some antivirus software blocks broadcast packets")
    print("  4. Corporate networks might filter Art-Net traffic")
    print("\nTo test manually:")
    print("  • Temporarily disable Windows Firewall")
    print("  • Use Wireshark to monitor 192.168.18.28:6454")
    print("  • Check if your Art-Net device is actually listening")

def main():
    """Test complet du réseau Art-Net"""
    print("=== ART-NET NETWORK DIAGNOSTIC ===")
    print("Testing connection to 192.168.18.28:6454\n")
    
    # Tests en séquence
    test_network_connectivity()
    
    if not test_socket_creation():
        print("\n✗ Socket issues detected. Aborting.")
        return
    
    packet = test_artnet_packet_construction()
    
    print(f"\n{'='*50}")
    print("SENDING TEST PACKETS - Monitor 192.168.18.28:6454 NOW!")
    print(f"{'='*50}")
    
    # Attendre que l'utilisateur soit prêt
    input("\nPress ENTER when ready to send packets...")
    
    test_raw_send(packet)
    
    print("\n" + "="*30)
    test_application_artnet()
    
    check_firewall()
    
    print(f"\n{'='*50}")
    print("DIAGNOSTIC COMPLETE")
    print("If you saw NO traffic on 192.168.18.28:6454,")
    print("check firewall settings and network configuration.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()