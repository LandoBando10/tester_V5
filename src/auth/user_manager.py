"""
User authentication and management
Desktop-friendly authentication without web complexity
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import bcrypt


class UserManager:
    """Manage user authentication and permissions"""
    
    def __init__(self, config_file: Path = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_file = config_file or Path("config/users.json")
        self.current_user = None
        self.current_role = None
        self.permissions = []
        
        # Load user configuration
        self.users = {}
        self.roles = {}
        self._load_config()
        
    def _load_config(self):
        """Load user configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.users = config.get('users', {})
                    self.roles = config.get('roles', {})
            else:
                # Create default config
                self._create_default_config()
        except Exception as e:
            self.logger.error(f"Error loading user config: {e}")
            
    def _create_default_config(self):
        """Create default user configuration"""
        # Default users with simple passwords (should be changed in production)
        default_config = {
            "users": {
                "admin": {
                    "password": "admin123",  # Plain text for initial setup
                    "role": "admin",
                    "full_name": "Administrator",
                    "created": datetime.now().isoformat()
                },
                "qe": {
                    "password": "quality123",  # Plain text for initial setup
                    "role": "qe",
                    "full_name": "Quality Engineer",
                    "created": datetime.now().isoformat()
                }
            },
            "roles": {
                "operator": {
                    "description": "Can run tests",
                    "permissions": ["run_tests"]
                },
                "qe": {
                    "description": "Quality Engineer",
                    "permissions": ["run_tests"]
                },
                "admin": {
                    "description": "Full administrative access",
                    "permissions": ["run_tests", "manage_users"]
                }
            }
        }
        
        # Save default config
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
            
        self.users = default_config['users']
        self.roles = default_config['roles']
        
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user with username and password"""
        if username not in self.users:
            self.logger.warning(f"Authentication failed - unknown user: {username}")
            return False
            
        user = self.users[username]
        
        # For initial setup, support plain text passwords
        if 'password' in user:
            # Plain text comparison (for development/initial setup)
            if user['password'] == password:
                self._set_current_user(username, user)
                return True
        elif 'password_hash' in user:
            # Bcrypt comparison (for production)
            try:
                if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                    self._set_current_user(username, user)
                    return True
            except Exception as e:
                self.logger.error(f"Error checking password hash: {e}")
                
        self.logger.warning(f"Authentication failed for user: {username}")
        return False
        
    def _set_current_user(self, username: str, user_data: Dict):
        """Set the current authenticated user"""
        self.current_user = username
        self.current_role = user_data.get('role', 'operator')
        self.permissions = self.roles.get(self.current_role, {}).get('permissions', [])
        
        self.logger.info(f"User authenticated: {username} (role: {self.current_role})")
        
    def has_permission(self, permission: str) -> bool:
        """Check if current user has a specific permission"""
        return permission in self.permissions
        
    def logout(self):
        """Logout current user"""
        self.logger.info(f"User logged out: {self.current_user}")
        self.current_user = None
        self.current_role = None
        self.permissions = []
        
    def get_current_user(self) -> Optional[str]:
        """Get current authenticated username"""
        return self.current_user
        
    def get_current_role(self) -> Optional[str]:
        """Get current user's role"""
        return self.current_role
        
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
    def add_user(self, username: str, password: str, role: str, full_name: str) -> bool:
        """Add a new user (admin only)"""
        if not self.has_permission('manage_users'):
            self.logger.error("Current user lacks permission to add users")
            return False
            
        if username in self.users:
            self.logger.error(f"User already exists: {username}")
            return False
            
        # Hash the password
        password_hash = self.hash_password(password)
        
        # Add user
        self.users[username] = {
            "password_hash": password_hash,
            "role": role,
            "full_name": full_name,
            "created": datetime.now().isoformat(),
            "created_by": self.current_user
        }
        
        # Save config
        self._save_config()
        self.logger.info(f"User added: {username} by {self.current_user}")
        return True
        
    def _save_config(self):
        """Save user configuration"""
        config = {
            "users": self.users,
            "roles": self.roles
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
            
    def log_action(self, action: str, details: Dict):
        """Log user action for audit trail"""
        audit_dir = Path("audit_logs")
        audit_dir.mkdir(exist_ok=True)
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user": self.current_user,
            "role": self.current_role,
            "action": action,
            "details": details
        }
        
        # Append to monthly audit file
        audit_file = audit_dir / f"audit_{datetime.now().strftime('%Y%m')}.json"
        
        try:
            if audit_file.exists():
                with open(audit_file, 'r') as f:
                    audit_data = json.load(f)
            else:
                audit_data = []
                
            audit_data.append(log_entry)
            
            with open(audit_file, 'w') as f:
                json.dump(audit_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error writing audit log: {e}")


# Global instance for the application
_user_manager = None


def get_user_manager() -> UserManager:
    """Get the global user manager instance"""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


# Example usage
if __name__ == "__main__":
    # Test the user manager
    manager = UserManager()
    
    # Test authentication
    if manager.authenticate("admin", "admin123"):
        print(f"Logged in as: {manager.get_current_user()}")
        print(f"Role: {manager.get_current_role()}")
        print(f"Permissions: {manager.permissions}")
        
        # Test permission check
        print(f"Can run tests: {manager.has_permission('run_tests')}")
        print(f"Can manage users: {manager.has_permission('manage_users')}")
        
        # Log an action
        manager.log_action("test_run", {
            "sku": "DD5001",
            "result": "Pass"
        })
    else:
        print("Authentication failed")