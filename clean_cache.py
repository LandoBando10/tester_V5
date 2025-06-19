"""
Quick script to clean up Python cache files
"""
import os
import shutil

def clean_pycache(root_dir='.'):
    """Remove all __pycache__ directories"""
    removed_count = 0
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        if '__pycache__' in dirnames:
            pycache_path = os.path.join(dirpath, '__pycache__')
            try:
                shutil.rmtree(pycache_path)
                print(f"Removed: {pycache_path}")
                removed_count += 1
            except Exception as e:
                print(f"Failed to remove {pycache_path}: {e}")
    
    print(f"\nTotal __pycache__ directories removed: {removed_count}")
    
    # Also remove any .pyc files that might be lingering
    pyc_count = 0
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.pyc'):
                filepath = os.path.join(dirpath, filename)
                try:
                    os.remove(filepath)
                    print(f"Removed .pyc file: {filepath}")
                    pyc_count += 1
                except Exception as e:
                    print(f"Failed to remove {filepath}: {e}")
    
    print(f"Total .pyc files removed: {pyc_count}")

if __name__ == "__main__":
    print("Cleaning Python cache files...")
    clean_pycache()
    print("\nDone! Please restart your application.")
