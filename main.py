"""
Light Light Show - Application principale
Spectacle de lumières synchronisé avec l'audio
"""

import sys
import os
import traceback
import tkinter as tk

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Configure le logging de base"""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('lightshow.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def main():
    """Point d'entrée principal de l'application"""
    logger = setup_logging()
    
    try:
        logger.info("Starting Light Light Show application")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Import et lancement de l'interface moderne
        from views.main_window import MainWindow
        
        # Créer et lancer l'application
        app = MainWindow()
        
        logger.info("Application initialized successfully")
        
        # Lancer la boucle principale
        app.mainloop()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("Application shutdown")

if __name__ == "__main__":
    main()