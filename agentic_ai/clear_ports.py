"""
Script to clear ports used by the AI Travel Planner
"""
import subprocess
import sys
import time

def clear_ports():
    """Clear ports 8000 and 8501 (backend and frontend)"""
    ports_to_clear = [8000, 8501]
    
    print("🧹 Clearing ports for AI Travel Planner...")
    print("=" * 50)
    
    for port in ports_to_clear:
        print(f"\n🔍 Checking port {port}...")
        
        try:
            # Find processes using the port
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True, 
                capture_output=True, 
                text=True
            )
            
            if result.stdout:
                print(f"📊 Port {port} is in use:")
                lines = result.stdout.strip().split('\n')
                pids = set()
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 5 and f':{port}' in parts[1]:
                        pid = parts[-1]
                        if pid.isdigit():
                            pids.add(pid)
                            print(f"   PID: {pid}")
                
                # Kill the processes
                for pid in pids:
                    try:
                        print(f"🔥 Terminating process {pid}...")
                        subprocess.run(f'taskkill /PID {pid} /F', shell=True, check=True)
                        print(f"✅ Process {pid} terminated")
                    except subprocess.CalledProcessError:
                        print(f"⚠️ Could not terminate process {pid} (may already be closed)")
                        
            else:
                print(f"✅ Port {port} is free")
                
        except Exception as e:
            print(f"❌ Error checking port {port}: {e}")
    
    print(f"\n⏳ Waiting 2 seconds for ports to clear...")
    time.sleep(2)
    
    # Verify ports are clear
    print(f"\n🔍 Verifying ports are clear...")
    for port in ports_to_clear:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        if result.stdout:
            print(f"⚠️ Port {port} still in use")
        else:
            print(f"✅ Port {port} is now free")
    
    print(f"\n🎉 Port clearing complete!")
    print(f"\n📋 Next steps:")
    print(f"   1. Start backend: python start_backend.py")
    print(f"   2. Start frontend: streamlit run app.py")

if __name__ == "__main__":
    clear_ports()
