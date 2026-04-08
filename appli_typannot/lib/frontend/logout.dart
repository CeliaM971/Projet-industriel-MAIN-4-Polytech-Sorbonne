import 'package:flutter/material.dart';
import 'saved_videos.dart';
import 'group_manager.dart';
import 'server.dart';

class LogoutHelper {
  // Méthode statique pour déconnecter l'utilisateur
  static Future<void> logout(BuildContext context) async {
    // Afficher une confirmation
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.logout, color: Colors.red),
            SizedBox(width: 12),
            Text('Déconnexion'),
          ],
        ),
        content: const Text('Voulez-vous vraiment vous déconnecter ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Annuler'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('Déconnecter'),
          ),
        ],
      ),
    );

    // Si l'utilisateur confirme
    if (confirm == true) {
      // Effacer les données de session
      final server = ServerConfig.instance;
      server.setToken('');
      server.setUserId(0);
      
      // Réinitialiser le groupe actuel
      GroupManager().currentGroup.value = Group(
        id: 0,
        name: "Espace personnel",
        isPersonal: true,
      );

      // Vider la liste des groupes et invitations
      GroupManager().userGroups.clear();
      GroupManager().invitations.clear();

      // Retourner à la page de login
      if (context.mounted) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          '/login',
          (route) => false, // Supprimer toutes les routes précédentes
        );
        
        // Afficher un message de confirmation
        Future.delayed(const Duration(milliseconds: 300), () {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Row(
                  children: [
                    Icon(Icons.check_circle, color: Colors.white),
                    SizedBox(width: 12),
                    Text('Déconnexion réussie'),
                  ],
                ),
                backgroundColor: Colors.green,
                duration: Duration(seconds: 2),
              ),
            );
          }
        });
      }
    }
  }

  // Méthode alternative pour déconnexion rapide sans confirmation
  static Future<void> quickLogout(BuildContext context) async {
    // Effacer les données de session
    final server = ServerConfig.instance;
    server.setToken('');
    server.setUserId(0);
    
    // Réinitialiser le groupe actuel
    GroupManager().currentGroup.value = Group(
      id: 0,
      name: "Espace personnel",
      isPersonal: true,
    );

    // Vider la liste des groupes et invitations
    GroupManager().userGroups.clear();
    GroupManager().invitations.clear();

    // Retourner à la page de login
    if (context.mounted) {
      Navigator.pushNamedAndRemoveUntil(
        context,
        '/login',
        (route) => false,
      );
    }
  }
}
