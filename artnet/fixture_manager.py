"""
Gestionnaire des fixtures d'éclairage
"""
from typing import Dict, List, Any, Optional

class FixtureManager:
    """Gestion des fixtures d'éclairage"""
    
    def __init__(self, fixtures_config: Dict):
        self.fixtures_config = fixtures_config
        
        # AJOUT : Vérifier et corriger la structure des fixtures
        self._validate_and_normalize_fixtures()
        
        print("✓ FixtureManager initialized")
    
    def _validate_and_normalize_fixtures(self):
        """Valide et normalise la structure des fixtures"""
        fixtures = self.fixtures_config.get('fixtures', [])
        
        for i, fixture in enumerate(fixtures):
            # Vérifier les champs obligatoires
            if 'name' not in fixture:
                print(f"[FIXTURE] Warning: Fixture {i} missing name")
                fixture['name'] = f"Fixture{i+1}"
            
            # Normaliser start_channel/startChannel
            if 'startChannel' in fixture and 'start_channel' not in fixture:
                fixture['start_channel'] = fixture['startChannel']
            elif 'start_channel' in fixture and 'startChannel' not in fixture:
                fixture['startChannel'] = fixture['start_channel']
            elif 'start_channel' not in fixture and 'startChannel' not in fixture:
                print(f"[FIXTURE] Warning: {fixture['name']} missing start_channel, using default")
                fixture['start_channel'] = fixture['startChannel'] = 1
            
            # Vérifier les autres champs
            if 'band' not in fixture:
                fixture['band'] = 'Bass'  # Valeur par défaut
            
            if 'responds_to_kicks' not in fixture:
                fixture['responds_to_kicks'] = False
        
        print(f"✓ Validated {len(fixtures)} fixtures")
    
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
    
    def get_fixture_by_name(self, fixture_name: str):
        """Récupère une fixture par son nom"""
        fixtures = self.fixtures_config.get('fixtures', [])
        for fixture in fixtures:
            if fixture.get('name') == fixture_name:
                # CORRECTION : Normaliser les noms des clés
                normalized_fixture = fixture.copy()
                
                # Assurer la cohérence des noms de clés
                if 'startChannel' in normalized_fixture and 'start_channel' not in normalized_fixture:
                    normalized_fixture['start_channel'] = normalized_fixture['startChannel']
                elif 'start_channel' in normalized_fixture and 'startChannel' not in normalized_fixture:
                    normalized_fixture['startChannel'] = normalized_fixture['start_channel']
                    
                return normalized_fixture
        return None
    
    def get_all_fixtures(self):
        """Retourne toutes les fixtures avec normalisation des clés"""
        fixtures = self.fixtures_config.get('fixtures', [])
        normalized_fixtures = []
        
        for fixture in fixtures:
            normalized_fixture = fixture.copy()
            
            # CORRECTION : Normaliser les noms des clés pour cohérence
            if 'startChannel' in normalized_fixture and 'start_channel' not in normalized_fixture:
                normalized_fixture['start_channel'] = normalized_fixture['startChannel']
            elif 'start_channel' in normalized_fixture and 'startChannel' not in normalized_fixture:
                normalized_fixture['startChannel'] = normalized_fixture['start_channel']
                
            normalized_fixtures.append(normalized_fixture)
            
        return normalized_fixtures
    
    def get_fixtures_for_band(self, band: str):
        """Retourne les fixtures d'une bande spécifique avec normalisation"""
        all_fixtures = self.get_all_fixtures()
        return [f for f in all_fixtures if f.get('band') == band]