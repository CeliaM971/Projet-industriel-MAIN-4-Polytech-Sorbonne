import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

import 'server.dart';

class Group {
  final int id;
  final String name;
  final String? description;
  final bool isPersonal;
  final int? ownerUserId;
  final String? ownerName;

  Group({
    required this.id,
    required this.name,
    this.description,
    required this.isPersonal,
    this.ownerUserId,
    this.ownerName,
  });

  factory Group.fromJson(Map<String, dynamic> json) {
    return Group(
      id: json['id'],
      name: json['name'],
      description: json['description'],
      isPersonal: json['is_personal'] ?? false,
      ownerUserId: json['owner_user_id'],
      ownerName: json['owner_name'],
    );
  }
}

class Invitation {
  final int id;
  final String groupName;
  final String inviterName;

  Invitation({required this.id, required this.groupName, required this.inviterName});

  factory Invitation.fromJson(Map<String, dynamic> json) {
    return Invitation(
      id: json['invitation_id'] ?? json['id'],
      groupName: json['group_name'] ?? "Groupe inconnu",
      inviterName: json['inviter_name'] ?? "Utilisateur inconnu",
    );
  }
}

class GroupManager {
  GroupManager._private();
  static final GroupManager _instance = GroupManager._private();
  factory GroupManager() => _instance;

  final ValueNotifier<Group> currentGroup = ValueNotifier<Group>(
    Group(id: 0, name: "Espace personnel", isPersonal: true),
  );

  final _server = ServerConfig.instance;

  List<Group> userGroups = [];
  List<Invitation> invitations = [];

  String get _baseUrl => _server.baseUrl;

  Map<String, String> _authHeaders() => _server.authHeaders();

  Future<void> loadUserGroups() async {
    final userId = _server.userId;
    if (userId == null) {
      print("❌ loadUserGroups: userId est null");
      return;
    }

    try {
      print("🔍 Chargement des groupes pour userId: $userId");
      final res = await http.get(
        Uri.parse("$_baseUrl/groups/users/$userId/groups"),
        headers: _authHeaders(),
      );
      print("📦 loadUserGroups Status: ${res.statusCode}");
      print("📦 loadUserGroups Body: ${res.body}");

      if (res.statusCode == 200) {
        final List data = jsonDecode(res.body);
        userGroups = data.map((g) => Group.fromJson(g)).toList();
        print("✅ ${userGroups.length} groupes chargés");

        final personalGroup = userGroups.firstWhere(
          (g) => g.isPersonal,
          orElse: () => Group(id: 0, name: "Espace personnel", isPersonal: true),
        );
        currentGroup.value = personalGroup;
        print("✅ Groupe actuel: ${currentGroup.value.name}");
      }
    } catch (e) {
      print("❌ Erreur loadUserGroups: $e");
    }
  }

  Future<Group?> createGroup(String name, {String? description}) async {
    try {
      print("🔍 Création du groupe: $name");
      final res = await http.post(
        Uri.parse("$_baseUrl/groups/"),
        headers: _authHeaders(),
        body: jsonEncode({"name": name, "description": description}),
      );
      print("📦 createGroup Status: ${res.statusCode}");
      print("📦 createGroup Body: ${res.body}");

      if (res.statusCode == 201) {
        final group = Group.fromJson(jsonDecode(res.body));
        userGroups.add(group);
        currentGroup.value = group;
        print("✅ Groupe créé: ${group.name} (ID: ${group.id})");
        return group;
      } else {
        print("❌ Erreur création groupe: ${res.body}");
      }
    } catch (e) {
      print("❌ Erreur createGroup: $e");
    }
    return null;
  }

  Future<bool> inviteUser(int groupId, String email) async {
    try {
      print("🔍 Invitation de $email au groupe $groupId");
      final res = await http.post(
        Uri.parse("$_baseUrl/invitations/groups/$groupId/invite"),
        headers: _authHeaders(),
        body: jsonEncode({"email": email}),
      );
      print("📧 inviteUser Status: ${res.statusCode}");
      print("📧 inviteUser Body: ${res.body}");

      final success = res.statusCode == 200 || res.statusCode == 201;
      if (success) {
        print("✅ Invitation envoyée avec succès");
      } else {
        print("❌ Échec de l'invitation");
      }
      return success;
    } catch (e) {
      print("❌ Erreur inviteUser: $e");
      return false;
    }
  }

  Future<void> loadInvitations() async {
    try {
      print("🔍 Chargement des invitations...");
      final res = await http.get(
        Uri.parse("$_baseUrl/invitations/me/invitations"),
        headers: _authHeaders(),
      );
      print("📩 loadInvitations Status: ${res.statusCode}");
      print("📩 loadInvitations Body: ${res.body}");

      if (res.statusCode == 200) {
        final List data = jsonDecode(res.body);
        invitations = data.map((i) => Invitation.fromJson(i)).toList();
        print("✅ ${invitations.length} invitations chargées");
        for (var inv in invitations) {
          print("   - Invitation ID ${inv.id}: ${inv.groupName} (par ${inv.inviterName})");
        }
      } else {
        print("❌ Erreur loadInvitations: ${res.body}");
      }
    } catch (e) {
      print("❌ Erreur loadInvitations: $e");
    }
  }

  Future<bool> respondToInvitation(int invitationId, String decision) async {
    try {
      print("🔍 Réponse à l'invitation $invitationId: $decision");
      final res = await http.post(
        Uri.parse("$_baseUrl/invitations/invitations/$invitationId/respond"),
        headers: _authHeaders(),
        body: jsonEncode({"decision": decision}),
      );
      print("📩 respondToInvitation Status: ${res.statusCode}");
      print("📩 respondToInvitation Body: ${res.body}");

      if (res.statusCode == 200) {
        invitations.removeWhere((inv) => inv.id == invitationId);
        print("✅ Réponse enregistrée");
        return true;
      }
    } catch (e) {
      print("❌ Erreur respondToInvitation: $e");
    }
    return false;
  }

  void selectGroup(Group group) {
    print("🔄 Sélection du groupe: ${group.name} (ID: ${group.id})");
    currentGroup.value = group;
  }

  Future<Map<String, dynamic>?> leaveGroup(int groupId, {int? newOwnerUserId}) async {
    try {
      final body = jsonEncode(
        newOwnerUserId == null ? {} : {"new_owner_user_id": newOwnerUserId},
      );

      final res = await http.post(
        Uri.parse("$_baseUrl/groups/$groupId/leave"),
        headers: _authHeaders(),
        body: body,
      );

      if (res.statusCode == 200) {
        return jsonDecode(res.body) as Map<String, dynamic>;
      } else {
        print("❌ leaveGroup error ${res.statusCode}: ${res.body}");
      }
    } catch (e) {
      print("❌ leaveGroup exception: $e");
    }
    return null;
  }

  Future<List<Map<String, dynamic>>> fetchGroupUsers(int groupId) async {
    try {
      final res = await http.get(
        Uri.parse("$_baseUrl/groups/$groupId/users"),
        headers: _authHeaders(),
      );

      if (res.statusCode == 200) {
        final List data = jsonDecode(res.body);
        return data.cast<Map<String, dynamic>>();
      } else {
        print("❌ fetchGroupUsers error ${res.statusCode}: ${res.body}");
      }
    } catch (e) {
      print("❌ fetchGroupUsers exception: $e");
    }
    return [];
  }

  Future<bool> deleteGroup(int groupId) async {
    try {
      final res = await http.delete(
        Uri.parse("$_baseUrl/groups/$groupId"),
        headers: _authHeaders(),
      );
      return res.statusCode == 200;
    } catch (e) {
      print("❌ deleteGroup exception: $e");
      return false;
    }
  }

  Future<bool> removeMember(int groupId, int userId) async {
    try {
      print("🔍 Retrait du membre $userId du groupe $groupId");
      final res = await http.delete(
        Uri.parse("$_baseUrl/groups/$groupId/members/$userId"),
        headers: _authHeaders(),
      );
      print("📦 removeMember Status: ${res.statusCode}");
      print("📦 removeMember Body: ${res.body}");

      if (res.statusCode == 200) {
        print("✅ Membre retiré avec succès");
        return true;
      } else {
        print("❌ Erreur retrait membre: ${res.body}");
        return false;
      }
    } catch (e) {
      print("❌ Erreur removeMember: $e");
      return false;
    }
  }

  Future<bool> renameGroup(int groupId, String newName, {String? newDescription}) async {
    try {
      print("🔍 Renommage du groupe $groupId: $newName");

      final body = <String, dynamic>{"name": newName};
      if (newDescription != null) body["description"] = newDescription;

      final res = await http.patch(
        Uri.parse("$_baseUrl/groups/$groupId"),
        headers: _authHeaders(),
        body: jsonEncode(body),
      );
      print("📦 renameGroup Status: ${res.statusCode}");
      print("📦 renameGroup Body: ${res.body}");

      if (res.statusCode == 200) {
        final updatedGroup = Group.fromJson(jsonDecode(res.body));
        final index = userGroups.indexWhere((g) => g.id == groupId);
        if (index != -1) {
          userGroups[index] = updatedGroup;
          if (currentGroup.value.id == groupId) {
            currentGroup.value = updatedGroup;
          }
        }
        print("✅ Groupe renommé avec succès");
        return true;
      } else {
        print("❌ Erreur renommage groupe: ${res.body}");
        return false;
      }
    } catch (e) {
      print("❌ Erreur renameGroup: $e");
      return false;
    }
  }
}
