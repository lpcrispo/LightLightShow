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
        
        # Import ici pour éviter les problèmes de dépendances circulaires
        from views.main_window import MainWindow
        
        # Créer et lancer l'application avec la signature existante
        app = MainWindow()
        
        logger.info("Application initialized successfully")
        
        # Lancer la boucle principale
        app.mainloop()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.error("Make sure all required modules are installed")
        # Fallback vers l'interface simple si disponible
        try:
            from ui import Application
            logger.info("Using fallback UI")
            app = Application()
            app.mainloop()
        except Exception as e2:
            logger.error(f"Fallback also failed: {e2}")
            raise
    except Exception as e:
        logger.error(f"Critical error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        logger.info("Application shutdown")

if __name__ == "__main__":
    main()