import 'package:flutter/material.dart';
import 'group_manager.dart';
import 'server.dart';

class GroupSelectionPage extends StatefulWidget {
  const GroupSelectionPage({super.key});

  @override
  State<GroupSelectionPage> createState() => _GroupSelectionPageState();
}

class _GroupSelectionPageState extends State<GroupSelectionPage> {
  final GroupManager _manager = GroupManager();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    await _manager.loadUserGroups();
    await _manager.loadInvitations();
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text("Gestion des groupes"),
          actions: [
            IconButton(
              icon: _isLoading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.refresh),
              onPressed: _isLoading ? null : _loadData,
              tooltip: "Rafraîchir",
            ),
          ],
          bottom: TabBar(
            tabs: [
              const Tab(icon: Icon(Icons.group), text: "Mes groupes"),
              Tab(
                icon: Badge(
                  label: Text('${_manager.invitations.length}'),
                  isLabelVisible: _manager.invitations.isNotEmpty,
                  child: const Icon(Icons.mail),
                ),
                text: "Invitations",
              ),
              const Tab(icon: Icon(Icons.add_circle), text: "Créer/Inviter"),
            ],
          ),
        ),
        body: TabBarView(
          children: [
            _buildMyGroupsTab(),
            _buildInvitationsTab(),
            _buildCreateInviteTab(),
          ],
        ),
      ),
    );
  }

  Widget _buildMyGroupsTab() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: _manager.userGroups.isEmpty
          ? const Center(
              child: Text("Aucun groupe disponible",
                  style: TextStyle(fontSize: 16, color: Colors.grey)),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _manager.userGroups.length,
              itemBuilder: (context, index) {
                final group = _manager.userGroups[index];
                final isSelected = _manager.currentGroup.value.id == group.id;

                return Card(
                  elevation: isSelected ? 4 : 1,
                  color: isSelected ? Colors.green[50] : null,
                  margin: const EdgeInsets.only(bottom: 12),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: group.isPersonal ? Colors.blue : Colors.purple,
                      child: Icon(
                        group.isPersonal ? Icons.person : Icons.group,
                        color: Colors.white,
                      ),
                    ),
                    title: Text(
                      group.name,
                      style: TextStyle(
                        fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                      ),
                    ),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (group.isPersonal)
                          const Text("Groupe personnel")
                        else if (group.ownerName != null)
                          Text("Créé par ${group.ownerName}")
                        else if (group.ownerUserId != null)
                          Text("Créé par l'utilisateur ${group.ownerUserId}"),
                      ],
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (isSelected) const Icon(Icons.check_circle, color: Colors.green),
                        if (!group.isPersonal)
                          IconButton(
                            icon: const Icon(Icons.settings),
                            onPressed: () => _showGroupOptions(group),
                          ),
                      ],
                    ),
                    onTap: () {
                      _manager.selectGroup(group);
                      setState(() {});
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(
                          content: Text("Groupe '${group.name}' sélectionné"),
                          duration: const Duration(seconds: 1),
                        ),
                      );
                    },
                  ),
                );
              },
            ),
    );
  }

  Widget _buildInvitationsTab() {
    return RefreshIndicator(
      onRefresh: _loadData,
      child: _manager.invitations.isEmpty
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.mail_outline, size: 64, color: Colors.grey[400]),
                  const SizedBox(height: 16),
                  const Text("Aucune invitation en attente",
                      style: TextStyle(fontSize: 16, color: Colors.grey)),
                  const SizedBox(height: 8),
                  TextButton.icon(
                    icon: const Icon(Icons.refresh),
                    label: const Text("Rafraîchir"),
                    onPressed: _loadData,
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _manager.invitations.length,
              itemBuilder: (context, index) {
                final inv = _manager.invitations[index];
                return Card(
                  color: Colors.amber[50],
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.group, color: Colors.orange),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                inv.groupName,
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            const Icon(Icons.person, size: 16, color: Colors.grey),
                            const SizedBox(width: 4),
                            Text("Invité par ${inv.inviterName}",
                                style: const TextStyle(color: Colors.grey)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.end,
                          children: [
                            TextButton.icon(
                              icon: const Icon(Icons.close, color: Colors.red),
                              label: const Text("Refuser"),
                              onPressed: () =>
                                  _respondToInvitation(inv.id, "declined", inv.groupName),
                            ),
                            const SizedBox(width: 8),
                            ElevatedButton.icon(
                              icon: const Icon(Icons.check),
                              label: const Text("Accepter"),
                              style: ElevatedButton.styleFrom(
                                backgroundColor: Colors.green,
                                foregroundColor: Colors.white,
                              ),
                              onPressed: () =>
                                  _respondToInvitation(inv.id, "accepted", inv.groupName),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
    );
  }

  Widget _buildCreateInviteTab() {
    final myUserId = ServerConfig.instance.userId; // 🔥 ServerConfig
    final currentGroup = _manager.currentGroup.value;
    final bool isOwner = (myUserId != null && currentGroup.ownerUserId == myUserId);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildSectionCard(
            title: "Créer un nouveau groupe",
            icon: Icons.add_circle,
            color: Colors.blue,
            child: Column(
              children: [
                const Text(
                  "Créez un groupe pour collaborer avec d'autres utilisateurs",
                  style: TextStyle(color: Colors.grey),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  icon: const Icon(Icons.group_add),
                  label: const Text("Créer un groupe"),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(double.infinity, 48),
                  ),
                  onPressed: _showCreateGroupDialog,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (!currentGroup.isPersonal && isOwner)
            _buildSectionCard(
              title: "Inviter dans '${currentGroup.name}'",
              icon: Icons.person_add,
              color: Colors.purple,
              child: Column(
                children: [
                  const Text(
                    "Invitez plusieurs utilisateurs à rejoindre ce groupe",
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.email),
                    label: const Text("Envoyer des invitations"),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 48),
                      backgroundColor: Colors.purple,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: _showInviteUserDialog,
                  ),
                ],
              ),
            )
          else if (!currentGroup.isPersonal && !isOwner)
            _buildSectionCard(
              title: "Invitations restreintes",
              icon: Icons.lock,
              color: Colors.orange,
              child: const Text(
                "Seul le propriétaire du groupe peut inviter de nouveaux membres.",
                style: TextStyle(color: Colors.grey),
                textAlign: TextAlign.center,
              ),
            )
          else
            _buildSectionCard(
              title: "Groupe personnel",
              icon: Icons.info_outline,
              color: Colors.orange,
              child: const Text(
                "Vous êtes actuellement dans votre groupe personnel. Sélectionnez ou créez un groupe partagé pour inviter d'autres utilisateurs.",
                style: TextStyle(color: Colors.grey),
                textAlign: TextAlign.center,
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required Color color,
    required Widget child,
  }) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: color,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            child,
          ],
        ),
      ),
    );
  }

  void _showCreateGroupDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Créer un nouveau groupe"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(
                labelText: "Nom du groupe *",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.group),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: descController,
              decoration: const InputDecoration(
                labelText: "Description (optionnel)",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.description),
              ),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Annuler"),
          ),
          ElevatedButton(
            onPressed: () async {
              final name = nameController.text.trim();
              if (name.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text("Le nom du groupe est obligatoire"),
                    backgroundColor: Colors.red,
                  ),
                );
                return;
              }

              Navigator.pop(context);

              final group = await _manager.createGroup(
                name,
                description: descController.text.trim().isEmpty
                    ? null
                    : descController.text.trim(),
              );

              if (group != null) {
                setState(() {});
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text("Groupe '${group.name}' créé avec succès !"),
                      backgroundColor: Colors.green,
                    ),
                  );
                }
              } else {
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text("Erreur lors de la création du groupe"),
                      backgroundColor: Colors.red,
                    ),
                  );
                }
              }
            },
            child: const Text("Créer"),
          ),
        ],
      ),
    );
  }

  void _showInviteUserDialog() {
    final emailController = TextEditingController();
    final List<String> successEmails = [];
    final List<String> failedEmails = [];

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (dialogContext, setDialogState) {
          return AlertDialog(
            title: Text("Inviter dans '${_manager.currentGroup.value.name}'"),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text("Entrez les emails un par un :",
                      style: TextStyle(color: Colors.grey)),
                  const SizedBox(height: 16),
                  if (successEmails.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.green[50],
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.green),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.check_circle, color: Colors.green, size: 20),
                              SizedBox(width: 8),
                              Text("Invitations envoyées :",
                                  style: TextStyle(
                                      fontWeight: FontWeight.bold, color: Colors.green)),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ...successEmails.map((email) => Padding(
                                padding: const EdgeInsets.only(left: 28, top: 4),
                                child: Text("• $email"),
                              )),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  if (failedEmails.isNotEmpty) ...[
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red[50],
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.red),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.error, color: Colors.red, size: 20),
                              SizedBox(width: 8),
                              Text("Erreurs :",
                                  style: TextStyle(
                                      fontWeight: FontWeight.bold, color: Colors.red)),
                            ],
                          ),
                          const SizedBox(height: 8),
                          ...failedEmails.map((email) => Padding(
                                padding: const EdgeInsets.only(left: 28, top: 4),
                                child: Text("• $email"),
                              )),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: emailController,
                    decoration: const InputDecoration(
                      labelText: "Email",
                      border: OutlineInputBorder(),
                      prefixIcon: Icon(Icons.email),
                      hintText: "exemple@email.com",
                    ),
                    keyboardType: TextInputType.emailAddress,
                    onSubmitted: (_) async {
                      final email = emailController.text.trim();
                      if (email.isNotEmpty) {
                        final success = await _manager.inviteUser(
                          _manager.currentGroup.value.id,
                          email,
                        );
                        setDialogState(() {
                          if (success) successEmails.add(email);
                          else failedEmails.add(email);
                          emailController.clear();
                        });
                      }
                    },
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () {
                  Navigator.pop(dialogContext);
                  if (successEmails.isNotEmpty && mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text("${successEmails.length} invitation(s) envoyée(s)"),
                        backgroundColor: Colors.green,
                      ),
                    );
                  }
                },
                child: const Text("Fermer"),
              ),
              ElevatedButton.icon(
                icon: const Icon(Icons.send),
                label: const Text("Inviter"),
                onPressed: () async {
                  final email = emailController.text.trim();
                  if (email.isEmpty) return;
                  if (!email.contains('@')) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text("Email invalide"),
                        backgroundColor: Colors.red,
                        duration: Duration(seconds: 1),
                      ),
                    );
                    return;
                  }

                  final success = await _manager.inviteUser(
                    _manager.currentGroup.value.id,
                    email,
                  );
                  setDialogState(() {
                    if (success) successEmails.add(email);
                    else failedEmails.add(email);
                    emailController.clear();
                  });
                },
              ),
            ],
          );
        },
      ),
    );
  }

  void _showRenameGroupDialog(Group group) {
    final nameController = TextEditingController(text: group.name);
    final descController = TextEditingController(text: group.description);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text("Renommer le groupe"),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(
                labelText: "Nouveau nom *",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.group),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: descController,
              decoration: const InputDecoration(
                labelText: "Description",
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.description),
              ),
              maxLines: 3,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text("Annuler"),
          ),
          ElevatedButton(
            onPressed: () async {
              final newName = nameController.text.trim();
              if (newName.isEmpty) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text("Le nom ne peut pas être vide"),
                    backgroundColor: Colors.red,
                  ),
                );
                return;
              }
              Navigator.pop(context);
              final success = await _manager.renameGroup(
                group.id,
                newName,
                newDescription: descController.text.trim().isEmpty
                    ? null
                    : descController.text.trim(),
              );
              if (success && mounted) {
                setState(() {});
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text("Groupe renommé en '$newName'"),
                    backgroundColor: Colors.green,
                  ),
                );
              } else if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text("Erreur lors du renommage"),
                    backgroundColor: Colors.red,
                  ),
                );
              }
            },
            child: const Text("Renommer"),
          ),
        ],
      ),
    );
  }

  void _showGroupOptions(Group group) {
    final myUserId = ServerConfig.instance.userId; // 🔥 ServerConfig
    final bool isOwner = (myUserId != null && group.ownerUserId == myUserId);

    showModalBottomSheet(
      context: context,
      builder: (sheetContext) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (!group.isPersonal && isOwner) ...[
              ListTile(
                leading: const Icon(Icons.person_add, color: Colors.purple),
                title: const Text("Inviter un utilisateur"),
                onTap: () {
                  Navigator.pop(sheetContext);
                  _manager.selectGroup(group);
                  setState(() {});
                  _showInviteUserDialog();
                },
              ),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.people, color: Colors.blue),
                title: const Text("Gérer les membres"),
                onTap: () {
                  Navigator.pop(sheetContext);
                  _showManageMembersDialog(group);
                },
              ),
              const Divider(),
              ListTile(
                leading: const Icon(Icons.delete, color: Colors.red),
                title: const Text("Supprimer le groupe"),
                onTap: () async {
                  final confirm = await showDialog<bool>(
                    context: sheetContext,
                    builder: (dialogContext) => AlertDialog(
                      title: const Text("Supprimer le groupe ?"),
                      content: const Text("Cette action est irréversible."),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(dialogContext, false),
                          child: const Text("Annuler"),
                        ),
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
                          onPressed: () => Navigator.pop(dialogContext, true),
                          child: const Text("Supprimer"),
                        ),
                      ],
                    ),
                  );
                  if (confirm != true) return;
                  Navigator.pop(sheetContext);
                  final ok = await _manager.deleteGroup(group.id);
                  if (ok && mounted) {
                    await _loadData();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                          content: Text("Groupe supprimé"),
                          backgroundColor: Colors.green),
                    );
                  }
                },
              ),
              ListTile(
                leading: const Icon(Icons.swap_horiz, color: Colors.orange),
                title: const Text("Quitter le groupe (transférer l'owner)"),
                onTap: () async {
                  final users = await _manager.fetchGroupUsers(group.id);
                  final candidates =
                      users.where((u) => u["id"] != myUserId).toList();

                  if (candidates.isEmpty) {
                    if (!mounted) return;
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                            "Impossible : aucun autre membre à qui transférer"),
                        backgroundColor: Colors.red,
                      ),
                    );
                    return;
                  }

                  int? selectedUserId;
                  final confirm = await showDialog<bool>(
                    context: sheetContext,
                    builder: (dialogContext) => StatefulBuilder(
                      builder: (dialogContext, setStateDialog) => AlertDialog(
                        title: const Text("Choisir un nouvel owner"),
                        content: DropdownButtonFormField<int>(
                          value: selectedUserId,
                          decoration: const InputDecoration(
                            labelText: "Nouveau owner",
                            border: OutlineInputBorder(),
                          ),
                          items: candidates.map((u) {
                            final int id = u["id"];
                            final String name =
                                (u["name"] ?? "User $id").toString();
                            return DropdownMenuItem<int>(
                              value: id,
                              child: Text("$name (id: $id)"),
                            );
                          }).toList(),
                          onChanged: (val) =>
                              setStateDialog(() => selectedUserId = val),
                        ),
                        actions: [
                          TextButton(
                            onPressed: () => Navigator.pop(dialogContext, false),
                            child: const Text("Annuler"),
                          ),
                          ElevatedButton(
                            onPressed: selectedUserId == null
                                ? null
                                : () => Navigator.pop(dialogContext, true),
                            child: const Text("Transférer & Quitter"),
                          ),
                        ],
                      ),
                    ),
                  );

                  if (confirm != true || selectedUserId == null) return;
                  Navigator.pop(sheetContext);
                  final res = await _manager.leaveGroup(group.id,
                      newOwnerUserId: selectedUserId);
                  if (res != null && mounted) {
                    await _loadData();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                            "Owner transféré, vous avez quitté le groupe"),
                        backgroundColor: Colors.green,
                      ),
                    );
                  }
                },
              ),
            ],
            if (!group.isPersonal && !isOwner)
              ListTile(
                leading: const Icon(Icons.exit_to_app, color: Colors.orange),
                title: const Text("Quitter le groupe"),
                onTap: () async {
                  final confirm = await showDialog<bool>(
                    context: sheetContext,
                    builder: (dialogContext) => AlertDialog(
                      title: const Text("Quitter le groupe ?"),
                      content: const Text("Vous perdrez l'accès à ce groupe."),
                      actions: [
                        TextButton(
                          onPressed: () => Navigator.pop(dialogContext, false),
                          child: const Text("Annuler"),
                        ),
                        ElevatedButton(
                          onPressed: () => Navigator.pop(dialogContext, true),
                          child: const Text("Quitter"),
                        ),
                      ],
                    ),
                  );
                  if (confirm != true) return;
                  Navigator.pop(sheetContext);
                  final res = await _manager.leaveGroup(group.id);
                  if (res != null && mounted) {
                    await _loadData();
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text("Vous avez quitté le groupe"),
                        backgroundColor: Colors.green,
                      ),
                    );
                  }
                },
              ),
            ListTile(
              leading: const Icon(Icons.edit, color: Colors.blue),
              title: const Text("Renommer le groupe"),
              onTap: () {
                Navigator.pop(sheetContext);
                _showRenameGroupDialog(group);
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _respondToInvitation(
      int invId, String decision, String groupName) async {
    final success = await _manager.respondToInvitation(invId, decision);
    if (success) {
      setState(() {});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(decision == "accepted"
                ? "Vous avez rejoint le groupe '$groupName'"
                : "Invitation refusée"),
            backgroundColor:
                decision == "accepted" ? Colors.green : Colors.orange,
          ),
        );
        if (decision == "accepted") _loadData();
      }
    }
  }

  void _confirmRemoveMember(
    BuildContext dialogContext,
    Group group,
    int userId,
    String userName,
  ) async {
    final confirm = await showDialog<bool>(
      context: dialogContext,
      builder: (confirmContext) => AlertDialog(
        title: const Text("Retirer ce membre ?"),
        content: Text(
          "Voulez-vous retirer '$userName' du groupe ?\n\nL'utilisateur recevra une notification.",
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(confirmContext, false),
            child: const Text("Annuler"),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(confirmContext, true),
            child: const Text("Retirer"),
          ),
        ],
      ),
    );

    if (confirm != true) return;
    final success = await _manager.removeMember(group.id, userId);
    if (!mounted) return;

    if (success) {
      Navigator.pop(dialogContext);
      await _loadData();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("'$userName' a été retiré du groupe"),
          backgroundColor: Colors.green,
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("Erreur lors du retrait du membre"),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  void _showManageMembersDialog(Group group) async {
    final myUserId = ServerConfig.instance.userId; // 🔥 ServerConfig
    final users = await _manager.fetchGroupUsers(group.id);
    if (!mounted) return;

    showDialog(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text("Membres de '${group.name}'"),
        content: SizedBox(
          width: double.maxFinite,
          child: users.isEmpty
              ? const Text("Aucun membre dans ce groupe")
              : ListView.builder(
                  shrinkWrap: true,
                  itemCount: users.length,
                  itemBuilder: (context, index) {
                    final user = users[index];
                    final int userId = user["id"];
                    final String userName =
                        (user["name"] ?? "User $userId").toString();
                    final bool isCurrentUser = userId == myUserId;
                    final bool isOwner = userId == group.ownerUserId;

                    return ListTile(
                      leading: CircleAvatar(
                        backgroundColor: isOwner ? Colors.orange : Colors.grey,
                        child: Icon(
                          isOwner ? Icons.star : Icons.person,
                          color: Colors.white,
                          size: 20,
                        ),
                      ),
                      title: Text(
                        userName,
                        style: TextStyle(
                          fontWeight: isCurrentUser
                              ? FontWeight.bold
                              : FontWeight.normal,
                        ),
                      ),
                      subtitle: Text(
                        isOwner
                            ? "Propriétaire"
                            : isCurrentUser
                                ? "Vous"
                                : "Membre",
                        style: TextStyle(
                            color: isOwner ? Colors.orange : Colors.grey),
                      ),
                      trailing: (!isCurrentUser && !isOwner)
                          ? IconButton(
                              icon: const Icon(Icons.person_remove,
                                  color: Colors.red),
                              onPressed: () => _confirmRemoveMember(
                                dialogContext,
                                group,
                                userId,
                                userName,
                              ),
                            )
                          : null,
                    );
                  },
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text("Fermer"),
          ),
        ],
      ),
    );
  }
}
