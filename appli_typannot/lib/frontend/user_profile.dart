import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'server.dart';
import 'logout.dart';
import 'group_manager.dart';

class UserProfile {
  final int id;
  final String name;
  final String email;
  final String number;
  final int? age;
  final bool isActive;
  final DateTime createdAt;

  UserProfile({
    required this.id,
    required this.name,
    required this.email,
    required this.number,
    this.age,
    required this.isActive,
    required this.createdAt,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'],
      name: json['name'],
      email: json['email'],
      number: json['number'],
      age: json['age'],
      isActive: json['is_active'] ?? true,
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }
}

class UserProfileScreen extends StatefulWidget {
  const UserProfileScreen({super.key});

  @override
  State<UserProfileScreen> createState() => _UserProfileScreenState();
}

class _UserProfileScreenState extends State<UserProfileScreen> {
  UserProfile? _userProfile;
  List<Group> _userGroups = [];
  bool _isLoading = true;
  bool _isLoadingGroups = false;
  String? _errorMessage;
  final GroupManager _groupManager = GroupManager();
  final _server = ServerConfig.instance;

  @override
  void initState() {
    super.initState();
    _loadUserProfile();
    _loadUserGroups();
  }

  Future<void> _loadUserProfile() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final userId = _server.userId;
      if (userId == null) throw Exception("Utilisateur non connecté");

      print("🔍 Chargement du profil utilisateur $userId");

      final response = await http.get(
        Uri.parse("${_server.baseUrl}/users/$userId"),
        headers: _server.authHeaders(),
      );

      print("📦 Status: ${response.statusCode}");
      print("📦 Body: ${response.body}");

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _userProfile = UserProfile.fromJson(data);
          _isLoading = false;
        });
        print("✅ Profil chargé avec succès");
      } else {
        throw Exception("Erreur ${response.statusCode}: ${response.body}");
      }
    } catch (e) {
      print("❌ Erreur lors du chargement du profil: $e");
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _loadUserGroups() async {
    setState(() => _isLoadingGroups = true);

    try {
      final userId = _server.userId;
      if (userId == null) throw Exception("Utilisateur non connecté");

      print("🔍 Chargement des groupes de l'utilisateur $userId");

      final response = await http.get(
        Uri.parse("${_server.baseUrl}/groups/users/$userId/groups"),
        headers: _server.authHeaders(),
      );

      print("📦 Groups Status: ${response.statusCode}");
      print("📦 Groups Body: ${response.body}");

      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        setState(() {
          _userGroups = data.map((g) => Group.fromJson(g)).toList();
          _isLoadingGroups = false;
        });
        print("✅ ${_userGroups.length} groupes chargés");
      } else {
        throw Exception("Erreur ${response.statusCode}: ${response.body}");
      }
    } catch (e) {
      print("❌ Erreur lors du chargement des groupes: $e");
      setState(() => _isLoadingGroups = false);
    }
  }

  Future<void> _editProfile() async {
    if (_userProfile == null) return;
    final result = await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => EditProfileScreen(userProfile: _userProfile!),
      ),
    );
    if (result == true) _loadUserProfile();
  }

  Future<void> _refreshAll() async {
    await Future.wait([_loadUserProfile(), _loadUserGroups()]);
  }

  String _formatDate(DateTime date) {
    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mon profil'),
        actions: [
          if (_userProfile != null)
            IconButton(
              icon: const Icon(Icons.edit),
              tooltip: 'Modifier le profil',
              onPressed: _editProfile,
            ),
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Déconnexion',
            onPressed: () => LogoutHelper.logout(context),
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.error_outline, size: 80, color: Colors.red[300]),
                      const SizedBox(height: 16),
                      Text('Erreur de chargement',
                          style: TextStyle(fontSize: 18, color: Colors.grey[600])),
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 32),
                        child: Text(_errorMessage!,
                            style: const TextStyle(color: Colors.red),
                            textAlign: TextAlign.center),
                      ),
                      const SizedBox(height: 24),
                      ElevatedButton.icon(
                        onPressed: _refreshAll,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Réessayer'),
                      ),
                    ],
                  ),
                )
              : _userProfile == null
                  ? const Center(child: Text('Aucun profil trouvé'))
                  : RefreshIndicator(
                      onRefresh: _refreshAll,
                      child: SingleChildScrollView(
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Center(
                              child: Column(
                                children: [
                                  CircleAvatar(
                                    radius: 60,
                                    backgroundColor: Theme.of(context).colorScheme.primary,
                                    child: Text(
                                      _userProfile!.name.isNotEmpty
                                          ? _userProfile!.name[0].toUpperCase()
                                          : '?',
                                      style: const TextStyle(
                                        fontSize: 48,
                                        color: Colors.white,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    _userProfile!.name,
                                    style: const TextStyle(
                                        fontSize: 28, fontWeight: FontWeight.bold),
                                  ),
                                  const SizedBox(height: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 12, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: _userProfile!.isActive
                                          ? Colors.green[100]
                                          : Colors.red[100],
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          _userProfile!.isActive
                                              ? Icons.check_circle
                                              : Icons.cancel,
                                          size: 16,
                                          color: _userProfile!.isActive
                                              ? Colors.green[700]
                                              : Colors.red[700],
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          _userProfile!.isActive ? 'Actif' : 'Inactif',
                                          style: TextStyle(
                                            color: _userProfile!.isActive
                                                ? Colors.green[700]
                                                : Colors.red[700],
                                            fontWeight: FontWeight.bold,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 32),
                            _buildSectionTitle('Informations personnelles'),
                            const SizedBox(height: 16),
                            _buildInfoCard(
                              icon: Icons.email,
                              label: 'Email',
                              value: _userProfile!.email,
                              color: Colors.blue,
                            ),
                            _buildInfoCard(
                              icon: Icons.phone,
                              label: 'Téléphone',
                              value: _userProfile!.number,
                              color: Colors.green,
                            ),
                            if (_userProfile!.age != null)
                              _buildInfoCard(
                                icon: Icons.cake,
                                label: 'Âge',
                                value: '${_userProfile!.age} ans',
                                color: Colors.orange,
                              ),
                            const SizedBox(height: 24),
                            _buildSectionTitle('Informations du compte'),
                            const SizedBox(height: 16),
                            _buildInfoCard(
                              icon: Icons.badge,
                              label: 'ID utilisateur',
                              value: '#${_userProfile!.id}',
                              color: Colors.purple,
                            ),
                            const SizedBox(height: 16),
                            _buildGroupsSection(),
                            const SizedBox(height: 32),
                            SizedBox(
                              width: double.infinity,
                              child: ElevatedButton.icon(
                                onPressed: _editProfile,
                                icon: const Icon(Icons.edit),
                                label: const Text('Modifier mon profil'),
                                style: ElevatedButton.styleFrom(
                                    padding: const EdgeInsets.symmetric(vertical: 16)),
                              ),
                            ),
                            const SizedBox(height: 12),
                            SizedBox(
                              width: double.infinity,
                              child: OutlinedButton.icon(
                                onPressed: () => LogoutHelper.logout(context),
                                icon: const Icon(Icons.logout, color: Colors.red),
                                label: const Text('Se déconnecter',
                                    style: TextStyle(color: Colors.red)),
                                style: OutlinedButton.styleFrom(
                                  side: const BorderSide(color: Colors.red),
                                  padding: const EdgeInsets.symmetric(vertical: 16),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(title,
        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold));
  }

  Widget _buildInfoCard({
    required IconData icon,
    required String label,
    required String value,
    required Color color,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                          fontWeight: FontWeight.w500)),
                  const SizedBox(height: 4),
                  Text(value,
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.bold)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGroupsSection() {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.indigo.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(Icons.groups, color: Colors.indigo, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Mes groupes',
                          style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                              fontWeight: FontWeight.w500)),
                      const SizedBox(height: 4),
                      Text('${_userGroups.length} groupe(s)',
                          style: const TextStyle(
                              fontSize: 16, fontWeight: FontWeight.bold)),
                    ],
                  ),
                ),
                if (_isLoadingGroups)
                  const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2))
                else
                  IconButton(
                    icon: const Icon(Icons.refresh),
                    onPressed: _loadUserGroups,
                    tooltip: 'Rafraîchir les groupes',
                  ),
              ],
            ),
            if (_userGroups.isNotEmpty) ...[
              const SizedBox(height: 16),
              const Divider(),
              const SizedBox(height: 12),
              ..._userGroups.map((group) {
                final isCurrentGroup =
                    _groupManager.currentGroup.value.id == group.id;
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    color: isCurrentGroup ? Colors.indigo[50] : Colors.grey[100],
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: isCurrentGroup ? Colors.indigo : Colors.grey[300]!,
                      width: isCurrentGroup ? 2 : 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        group.isPersonal ? Icons.person : Icons.group,
                        size: 20,
                        color: isCurrentGroup ? Colors.indigo : Colors.grey[600],
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              group.name,
                              style: TextStyle(
                                fontWeight: isCurrentGroup
                                    ? FontWeight.bold
                                    : FontWeight.normal,
                                color: isCurrentGroup
                                    ? Colors.indigo[900]
                                    : Colors.black87,
                              ),
                            ),
                            if (group.isPersonal)
                              Text('Personnel',
                                  style: TextStyle(
                                      fontSize: 11, color: Colors.grey[600])),
                          ],
                        ),
                      ),
                      if (isCurrentGroup)
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.indigo,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Text('Actuel',
                              style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 11,
                                  fontWeight: FontWeight.bold)),
                        ),
                    ],
                  ),
                );
              }),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () =>
                      Navigator.pushNamed(context, '/group_selection'),
                  icon: const Icon(Icons.settings),
                  label: const Text('Gérer mes groupes'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.indigo,
                    side: const BorderSide(color: Colors.indigo),
                  ),
                ),
              ),
            ] else if (!_isLoadingGroups) ...[
              const SizedBox(height: 12),
              Center(
                child: Text('Aucun groupe',
                    style: TextStyle(
                        color: Colors.grey[600],
                        fontStyle: FontStyle.italic)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

// =====================================================
// PAGE D'ÉDITION DU PROFIL
// =====================================================

class EditProfileScreen extends StatefulWidget {
  final UserProfile userProfile;

  const EditProfileScreen({super.key, required this.userProfile});

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  late TextEditingController _nameController;
  late TextEditingController _emailController;
  late TextEditingController _numberController;
  late TextEditingController _ageController;

  bool _isSaving = false;
  final _formKey = GlobalKey<FormState>();
  final _server = ServerConfig.instance;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.userProfile.name);
    _emailController = TextEditingController(text: widget.userProfile.email);
    _numberController = TextEditingController(text: widget.userProfile.number);
    _ageController =
        TextEditingController(text: widget.userProfile.age?.toString() ?? '');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _numberController.dispose();
    _ageController.dispose();
    super.dispose();
  }

  Future<void> _saveChanges() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isSaving = true);

    try {
      final userId = _server.userId;
      if (userId == null) throw Exception("Utilisateur non connecté");

      final updateData = <String, dynamic>{};

      if (_nameController.text != widget.userProfile.name)
        updateData['name'] = _nameController.text;
      if (_emailController.text != widget.userProfile.email)
        updateData['email'] = _emailController.text;
      if (_numberController.text != widget.userProfile.number)
        updateData['number'] = _numberController.text;

      final ageText = _ageController.text.trim();
      if (ageText.isNotEmpty) {
        final age = int.tryParse(ageText);
        if (age != null && age != widget.userProfile.age) {
          updateData['age'] = age;
        }
      }

      if (updateData.isEmpty) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Aucune modification détectée'),
              backgroundColor: Colors.orange,
            ),
          );
          Navigator.pop(context, false);
        }
        return;
      }

      print("📤 Envoi des modifications: $updateData");

      final response = await http.patch(
        Uri.parse("${_server.baseUrl}/users/$userId"),
        headers: _server.authHeaders(),
        body: jsonEncode(updateData),
      );

      print("📦 Status: ${response.statusCode}");
      print("📦 Body: ${response.body}");

      if (response.statusCode == 200) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Row(children: [
                Icon(Icons.check_circle, color: Colors.white),
                SizedBox(width: 12),
                Text('Profil mis à jour avec succès'),
              ]),
              backgroundColor: Colors.green,
            ),
          );
          Navigator.pop(context, true);
        }
      } else {
        throw Exception("Erreur ${response.statusCode}: ${response.body}");
      }
    } catch (e) {
      print("❌ Erreur lors de la mise à jour: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur: $e'), backgroundColor: Colors.red),
        );
      }
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Modifier mon profil'),
        actions: [
          if (!_isSaving)
            IconButton(
              icon: const Icon(Icons.check),
              tooltip: 'Sauvegarder',
              onPressed: _saveChanges,
            ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Center(
              child: Stack(
                children: [
                  CircleAvatar(
                    radius: 60,
                    backgroundColor: Theme.of(context).colorScheme.primary,
                    child: Text(
                      _nameController.text.isNotEmpty
                          ? _nameController.text[0].toUpperCase()
                          : '?',
                      style: const TextStyle(
                          fontSize: 48,
                          color: Colors.white,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: Theme.of(context).colorScheme.primary,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.edit, color: Colors.white, size: 20),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
            TextFormField(
              controller: _nameController,
              decoration: const InputDecoration(
                labelText: 'Nom *',
                prefixIcon: Icon(Icons.person),
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty)
                  return 'Le nom est obligatoire';
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _emailController,
              decoration: const InputDecoration(
                labelText: 'Email *',
                prefixIcon: Icon(Icons.email),
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.emailAddress,
              validator: (value) {
                if (value == null || value.trim().isEmpty)
                  return 'L\'email est obligatoire';
                if (!value.contains('@')) return 'Email invalide';
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _numberController,
              decoration: const InputDecoration(
                labelText: 'Téléphone *',
                prefixIcon: Icon(Icons.phone),
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.phone,
              validator: (value) {
                if (value == null || value.trim().isEmpty)
                  return 'Le téléphone est obligatoire';
                if (value.length < 10)
                  return 'Le numéro doit contenir au moins 10 chiffres';
                return null;
              },
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _ageController,
              decoration: const InputDecoration(
                labelText: 'Âge',
                prefixIcon: Icon(Icons.cake),
                border: OutlineInputBorder(),
                hintText: 'Optionnel',
              ),
              keyboardType: TextInputType.number,
              validator: (value) {
                if (value != null && value.isNotEmpty) {
                  final age = int.tryParse(value);
                  if (age == null || age < 0 || age > 150) return 'Âge invalide';
                }
                return null;
              },
            ),
            const SizedBox(height: 32),
            SizedBox(
              height: 50,
              child: ElevatedButton.icon(
                onPressed: _isSaving ? null : _saveChanges,
                icon: _isSaving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.save),
                label: Text(
                    _isSaving ? 'Sauvegarde...' : 'Sauvegarder les modifications'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.green,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 50,
              child: OutlinedButton.icon(
                onPressed: _isSaving ? null : () => Navigator.pop(context, false),
                icon: const Icon(Icons.cancel),
                label: const Text('Annuler'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
