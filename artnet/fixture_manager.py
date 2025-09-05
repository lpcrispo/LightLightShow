"""
Gestionnaire des fixtures d'éclairage
"""
from typing import Dict, List, Any, Optional

class FixtureManager:
    """Gestion des fixtures d'éclairage"""
    
    def __init__(self, fixtures_config: Dict):
        self.fixtures_config = fixtures_config
    
    def get_fixtures_by_criteria(self, band: Optional[str] = None, 
                               responds_to_kicks: Optional[bool] = None) -> List[Dict]:
        """Retourne les fixtures selon des critères spécifiques"""
        fixtures = []
        
        for fixture in self.fixtures_config['fixtures']:
            # Filtrer par bande
            if band is not None and fixture.get('band') != band:
                continue
                
            # Filtrer par réponse aux kicks
            if responds_to_kicks is not None and fixture.get('responds_to_kicks') != responds_to_kicks:
                continue
                
            fixtures.append(fixture)
        
        return fixtures
    
    def get_fixture_by_name(self, name: str) -> Optional[Dict]:
        """Récupère une fixture par son nom"""
        return next((f for f in self.fixtures_config['fixtures'] if f['name'] == name), None)
    
    def get_all_fixtures(self) -> List[Dict]:
        """Retourne toutes les fixtures"""
        return self.fixtures_config['fixtures']
    
    def get_fixtures_for_band(self, band: str) -> List[Dict]:
        """Retourne toutes les fixtures d'une bande"""
        return self.get_fixtures_by_criteria(band=band)