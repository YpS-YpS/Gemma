# backend/core/game_manager.py
"""
Game configuration management for the new backend system
"""

import os
import glob
import yaml
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GameConfig:
    """Game configuration data structure"""
    name: str
    path: str
    config_type: str  # 'steps' or 'state_machine'
    benchmark_duration: int
    resolution: str
    preset: str
    yaml_path: str
    last_modified: Optional[datetime] = None


class GameConfigManager:
    """Manages game configurations for the backend"""
    
    def __init__(self, config_dir: str = "config/games"):
        self.config_dir = config_dir
        self.games: Dict[str, GameConfig] = {}
        self._ensure_config_dir()
        self.load_configurations()
        
        logger.info(f"GameConfigManager initialized with {len(self.games)} configurations")
    
    def _ensure_config_dir(self):
        """Ensure the configuration directory exists"""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
            logger.info(f"Created game config directory: {self.config_dir}")
    
    def load_configurations(self) -> int:
        """
        Load all game configurations from YAML files
        
        Returns:
            Number of configurations loaded
        """
        self.games.clear()
        
        # Find all YAML files in the config directory
        yaml_patterns = [
            os.path.join(self.config_dir, "*.yaml"),
            os.path.join(self.config_dir, "*.yml")
        ]
        
        yaml_files = []
        for pattern in yaml_patterns:
            yaml_files.extend(glob.glob(pattern))
        
        if not yaml_files:
            logger.warning(f"No YAML configuration files found in {self.config_dir}")
            return 0
        
        loaded_count = 0
        for yaml_file in yaml_files:
            try:
                if self._load_single_config(yaml_file):
                    loaded_count += 1
            except Exception as e:
                logger.error(f"Failed to load config {yaml_file}: {str(e)}")
        
        logger.info(f"Loaded {loaded_count} game configurations from {len(yaml_files)} files")
        return loaded_count
    
    def _load_single_config(self, yaml_file: str) -> bool:
        """
        Load a single game configuration file
        
        Args:
            yaml_file: Path to the YAML file
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                logger.warning(f"Empty configuration file: {yaml_file}")
                return False
            
            # Extract metadata
            metadata = config_data.get('metadata', {})
            
            # Determine game name
            game_name = metadata.get('game_name')
            if not game_name:
                # Fallback to filename without extension
                game_name = os.path.basename(yaml_file)
                for ext in ['.yaml', '.yml']:
                    if game_name.endswith(ext):
                        game_name = game_name[:-len(ext)]
                        break
            
            # Determine configuration type
            config_type = 'steps' if 'steps' in config_data else 'state_machine'
            
            # Get file modification time
            stat = os.stat(yaml_file)
            last_modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Create game configuration
            game_config = GameConfig(
                name=game_name,
                path=metadata.get('path', ''),
                config_type=config_type,
                benchmark_duration=metadata.get('benchmark_duration', 120),
                resolution=metadata.get('resolution', '1920x1080'),
                preset=metadata.get('preset', 'High'),
                yaml_path=yaml_file,
                last_modified=last_modified
            )
            
            # Store the configuration
            self.games[game_name] = game_config
            logger.debug(f"Loaded game config: {game_name} ({config_type}) from {yaml_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration {yaml_file}: {str(e)}")
            return False
    
    def get_all_games(self) -> Dict[str, GameConfig]:
        """Get all loaded game configurations"""
        return self.games.copy()
    
    def get_game(self, name: str) -> Optional[GameConfig]:
        """Get a specific game configuration by name"""
        return self.games.get(name)
    
    def reload_configurations(self) -> Dict[str, Any]:
        """
        Reload all configurations and return statistics
        
        Returns:
            Dictionary with reload statistics
        """
        old_count = len(self.games)
        new_count = self.load_configurations()
        
        stats = {
            'status': 'success',
            'old_count': old_count,
            'new_count': new_count,
            'games': list(self.games.keys()),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Configuration reload: {old_count} -> {new_count} games")
        return stats
    
    def get_game_stats(self) -> Dict[str, Any]:
        """Get statistics about loaded games"""
        if not self.games:
            return {
                'total_games': 0,
                'config_types': {},
                'games': []
            }
        
        config_types = {}
        for game in self.games.values():
            config_types[game.config_type] = config_types.get(game.config_type, 0) + 1
        
        # Convert games to dict format with proper datetime handling
        games_list = []
        for game in self.games.values():
            game_dict = asdict(game)
            if game_dict.get('last_modified'):
                game_dict['last_modified'] = game.last_modified.isoformat()
            games_list.append(game_dict)
        
        return {
            'total_games': len(self.games),
            'config_types': config_types,
            'games': games_list
        }
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert all games to dictionary format for API/WebSocket"""
        result = {}
        for name, config in self.games.items():
            config_dict = asdict(config)
            # Convert datetime to ISO string for JSON serialization
            if config_dict.get('last_modified'):
                config_dict['last_modified'] = config.last_modified.isoformat()
            result[name] = config_dict
        return result