import tkinter as tk
from tkinter import ttk

class FixtureView(ttk.Frame):
    def __init__(self, parent, artnet_manager):
        super().__init__(parent)
        self.artnet_manager = artnet_manager
        self.fixture_canvas = {}
        self.fixture_labels = {}
        self.setup_ui()

    def setup_ui(self):
        fixture_frame = ttk.LabelFrame(self, text="Fixtures Status")
        fixture_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Organiser les fixtures par bande avec colonnes multiples
        band_names = ['Bass', 'Low-Mid', 'High-Mid', 'Treble']
        max_rows = 3  # Maximum de fixtures par colonne
        
        # Grouper les fixtures par bande
        fixtures_by_band = {band: [] for band in band_names}
        for fixture in self.artnet_manager.fixtures_config['fixtures']:
            band = fixture.get('band', 'Bass')
            if band in fixtures_by_band:
                fixtures_by_band[band].append(fixture)

        # Headers des bandes
        col_start = 0
        for band_idx, band in enumerate(band_names):
            fixtures = fixtures_by_band[band]
            num_fixtures = len(fixtures)
            
            # Calculer le nombre de colonnes nécessaires
            num_cols = max(1, (num_fixtures + max_rows - 1) // max_rows)
            
            # Header centré sur toutes les colonnes de cette bande
            header_label = ttk.Label(fixture_frame, text=f"{band} Band", 
                                   font=('Arial', 10, 'bold'))
            header_label.grid(row=0, column=col_start, columnspan=num_cols, 
                            padx=5, pady=5, sticky="ew")
            
            # Couleur de fond pour identifier la bande
            color_map = {'Bass': '#ffcccc', 'Low-Mid': '#ccffcc', 
                        'High-Mid': '#ccccff', 'Treble': '#ffccff'}
            try:
                header_label.configure(background=color_map.get(band, '#f0f0f0'))
            except:
                pass  # Ignore si le style ne supporte pas le background
            
            # Placer les fixtures dans cette bande
            for fixture_idx, fixture in enumerate(fixtures):
                # Calculer la position dans la grille
                col_offset = fixture_idx // max_rows
                row_in_col = fixture_idx % max_rows
                
                final_col = col_start + col_offset
                final_row = 1 + row_in_col  # +1 pour le header
                
                # Container pour la fixture
                frame = ttk.Frame(fixture_frame)
                frame.grid(row=final_row, column=final_col, padx=3, pady=3, sticky="n")
                
                # Nom de la fixture avec indicateur de kick (plus compact)
                name_text = fixture['name']  # Utiliser le nom complet
                if fixture.get('responds_to_kicks', False):
                    name_text += " 🥁"
                name_label = ttk.Label(frame, text=name_text, font=('Arial', 7))
                name_label.pack()

                # Canvas pour afficher la couleur (plus compact)
                canvas = tk.Canvas(frame, width=60, height=60, relief='sunken', borderwidth=1)
                canvas.pack(pady=1)
                self.fixture_canvas[fixture['name']] = canvas

                # Label pour afficher les valeurs RGBW (plus compact)
                value_label = ttk.Label(frame, text="R:0 G:0\nB:0 W:0", font=('Courier', 6))
                value_label.pack()
                self.fixture_labels[fixture['name']] = value_label

                # Info canal et kick (plus compact)
                info_text = f"Ch:{fixture['startChannel']}"
                if fixture.get('responds_to_kicks', False):
                    kick_sens = fixture.get('kick_sensitivity', 1.0)
                    info_text += f" K:{kick_sens:.1f}"
                channel_label = ttk.Label(frame, text=info_text, font=('Arial', 6))
                channel_label.pack()
            
            # Mettre à jour la position de départ pour la prochaine bande
            col_start += num_cols + 1  # +1 pour l'espacement entre bandes

        # Légende mise à jour (plus compacte)
        legend_frame = ttk.Frame(fixture_frame)
        legend_frame.grid(row=max_rows + 2, column=0, columnspan=col_start, pady=5)
        
        # Légende des couleurs
        for i, band in enumerate(band_names):
            color_map = {'Bass': 'red', 'Low-Mid': 'green', 'High-Mid': 'blue', 'Treble': 'purple'}
            legend_canvas = tk.Canvas(legend_frame, width=12, height=12, bg=color_map.get(band, 'gray'))
            legend_canvas.grid(row=0, column=i*2, padx=1)
            ttk.Label(legend_frame, text=band, font=('Arial', 7)).grid(row=0, column=i*2+1, padx=3)
        
        # Séparateur
        ttk.Separator(legend_frame, orient='vertical').grid(row=0, column=len(band_names)*2, padx=10, sticky='ns')
        
        # Légende pour les kicks
        ttk.Label(legend_frame, text="🥁=Kick", font=('Arial', 7)).grid(row=0, column=len(band_names)*2+1, padx=5)
        
        # Info sur la disposition
        info_text = f"Max {max_rows} fixtures per column"
        ttk.Label(legend_frame, text=info_text, font=('Arial', 6), foreground='gray').grid(
            row=1, column=0, columnspan=len(band_names)*2+2, pady=2)

    def update_display(self):
        """Met à jour l'affichage des fixtures avec les données Art-Net reçues"""
        try:
            fixture_values = self.artnet_manager.get_fixture_values()
            
            for name, values in fixture_values.items():
                if name in self.fixture_canvas:
                    # Debug des valeurs reçues pour les fixtures actives
                    total_brightness = sum(values.values())
                    #if total_brightness > 10:  # Seuil plus élevé pour réduire le spam
                        #print(f"[FIXTURE] {name}: R={values['red']} G={values['green']} "
                        #      f"B={values['blue']} W={values['white']}")
                    
                    # Calculer la couleur en tenant compte du blanc
                    r = values['red']
                    g = values['green'] 
                    b = values['blue']
                    w = values['white']
                    
                    # Ajouter le blanc aux autres couleurs pour un rendu plus réaliste
                    r_display = min(255, r + w)
                    g_display = min(255, g + w)
                    b_display = min(255, b + w)
                    
                    # Convertir en couleur hex
                    color = f'#{r_display:02x}{g_display:02x}{b_display:02x}'
                    
                    # Mettre à jour le canvas
                    self.fixture_canvas[name].configure(bg=color)
                    
                    # Mettre à jour le label avec les valeurs (format plus compact)
                    if name in self.fixture_labels:
                        value_text = f"R:{r:3d} G:{g:3d}\nB:{b:3d} W:{w:3d}"
                        self.fixture_labels[name].configure(text=value_text)
                        
        except Exception as e:
            print(f"Error updating fixture display: {e}")
            import traceback
            traceback.print_exc()

    def get_fixture_info(self, fixture_name):
        """Retourne les informations détaillées d'une fixture"""
        for fixture in self.artnet_manager.fixtures_config['fixtures']:
            if fixture['name'] == fixture_name:
                values = self.artnet_manager.get_fixture_values().get(fixture_name, {})
                return {
                    'name': fixture['name'],
                    'band': fixture.get('band', 'Unknown'),
                    'start_channel': fixture['startChannel'],
                    'values': values
                }
        return None

    def highlight_active_fixtures(self, band=None):
        """Surligne visuellement les fixtures actives d'une bande"""
        if not band:
            return
            
        for fixture in self.artnet_manager.fixtures_config['fixtures']:
            if fixture.get('band') == band and fixture['name'] in self.fixture_canvas:
                canvas = self.fixture_canvas[fixture['name']]
                # Ajouter un effet de surbrillance temporaire
                original_relief = canvas.cget('relief')
                canvas.configure(relief='raised', borderwidth=3)
                # Restaurer l'apparence normale après 200ms
                canvas.after(200, lambda c=canvas, r=original_relief: 
                           c.configure(relief=r, borderwidth=1))