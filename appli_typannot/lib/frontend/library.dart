import 'dart:io';
import 'package:flutter/material.dart';
import 'saved_videos.dart';
import 'group_manager.dart';

class SavedVideosLibraryScreen extends StatefulWidget {
  const SavedVideosLibraryScreen({super.key});

  @override
  State<SavedVideosLibraryScreen> createState() =>
      _SavedVideosLibraryScreenState();
}

class _SavedVideosLibraryScreenState extends State<SavedVideosLibraryScreen> {
  List<SavedVideoEntry> _videos = [];
  bool _isLoading = true;
  String? _pickMode;
  final GroupManager _groupManager = GroupManager();

  @override
  void initState() {
    super.initState();
    _loadVideos();
    _groupManager.currentGroup.addListener(_onGroupChanged);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (_pickMode == null && args is String) {
      _pickMode = args;
    }
  }

  @override
  void dispose() {
    _groupManager.currentGroup.removeListener(_onGroupChanged);
    super.dispose();
  }

  void _onGroupChanged() {
    print("🔄 Groupe changé dans library, rechargement des vidéos...");
    _loadVideos();
  }

  Future<void> _loadVideos() async {
    setState(() => _isLoading = true);
    try {
      final currentGroup = _groupManager.currentGroup.value;
      print("📂 Chargement des vidéos du groupe: ${currentGroup.name} (ID: ${currentGroup.id})");

      if (currentGroup.id == 0) {
        print("⚠️ Aucun groupe sélectionné");
        if (mounted) {
          setState(() {
            _videos = [];
            _isLoading = false;
          });
        }
        return;
      }

      final serverVideos = await SavedVideosService.instance.fetchGroupVideos(currentGroup.id);

      if (mounted) {
        setState(() {
          _videos = serverVideos;
          _isLoading = false;
        });
        print("✅ ${_videos.length} vidéos chargées pour le groupe");
      }
    } catch (e) {
      print("❌ Erreur lors du chargement des vidéos: $e");
      if (mounted) {
        setState(() => _isLoading = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erreur de chargement: $e')),
        );
      }
    }
  }

  Future<void> _renameVideo(SavedVideoEntry entry) async {
    final controller = TextEditingController(text: entry.name);
    final newName = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Renommer la vidéo'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Nouveau nom'),
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
          TextButton(onPressed: () => Navigator.pop(ctx, controller.text), child: const Text('Renommer')),
        ],
      ),
    );

    if (newName != null && newName.isNotEmpty && newName != entry.name) {
      try {
        await SavedVideosService.instance.renameVideo(entry.videoId, newName);
        _loadVideos();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('✅ Vidéo renommée'), backgroundColor: Colors.green),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('❌ Erreur: $e'), backgroundColor: Colors.red),
          );
        }
      }
    }
  }

  Future<void> _deleteVideo(SavedVideoEntry entry) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Supprimer la vidéo'),
        content: Text('Voulez-vous vraiment supprimer "${entry.name}" ?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      try {
        await SavedVideosService.instance.deleteVideo(entry.videoId);
        _loadVideos();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('✅ Vidéo supprimée'), backgroundColor: Colors.green),
          );
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('❌ Erreur: $e'), backgroundColor: Colors.red),
          );
        }
      }
    }
  }

  void _handleVideoTap(SavedVideoEntry entry) {
    print('🎬 Video sélectionnée: ${entry.name}, mode: $_pickMode');

    if (_pickMode == 'analysis') {
      print('🔬 Navigation vers /analysis');
      Navigator.pushNamed(
        context,
        '/analysis',
        arguments: {
          'videoId': entry.videoId,
          'cropRect': null,
        },
      );
    } else if (_pickMode == 'annotate') {
      print('📝 Navigation vers /annotate');
      Navigator.pushNamed(
        context,
        '/annotate',
        arguments: {
          'videoId': entry.videoId,
          'cropRect': null,
        },
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Vidéo sélectionnée : ${entry.name}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: ValueListenableBuilder<Group>(
          valueListenable: _groupManager.currentGroup,
          builder: (context, group, child) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _pickMode == 'analysis'
                      ? 'Choisir une vidéo à analyser'
                      : _pickMode == 'annotate'
                          ? 'Choisir une vidéo à annoter'
                          : 'Mes vidéos sauvegardées',
                  style: const TextStyle(fontSize: 18),
                ),
                Text(group.name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.normal)),
              ],
            );
          },
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _loadVideos, tooltip: 'Rafraîchir'),
          IconButton(
            icon: const Icon(Icons.group),
            onPressed: () => Navigator.pushNamed(context, '/group_selection'),
            tooltip: 'Changer de groupe',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _videos.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.video_library_outlined, size: 80, color: Colors.grey[400]),
                      const SizedBox(height: 16),
                      ValueListenableBuilder<Group>(
                        valueListenable: _groupManager.currentGroup,
                        builder: (context, group, child) {
                          return Text(
                            group.id == 0
                                ? 'Sélectionnez un groupe pour voir les vidéos'
                                : 'Aucune vidéo dans "${group.name}"',
                            style: TextStyle(fontSize: 16, color: Colors.grey[600]),
                            textAlign: TextAlign.center,
                          );
                        },
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: () => Navigator.pushNamed(context, '/group_selection'),
                        icon: const Icon(Icons.group),
                        label: const Text('Choisir un groupe'),
                      ),
                    ],
                  ),
                )
              : Column(
                  children: [
                    ValueListenableBuilder<Group>(
                      valueListenable: _groupManager.currentGroup,
                      builder: (context, group, child) {
                        return Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          color: Colors.blue[50],
                          child: Row(
                            children: [
                              Icon(Icons.info_outline, color: Colors.blue[700]),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Text(
                                  '${_videos.length} vidéo(s) disponible(s) dans "${group.name}"',
                                  style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blue[900]),
                                ),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                    Expanded(
                      child: ListView.builder(
                        itemCount: _videos.length,
                        padding: const EdgeInsets.all(8),
                        itemBuilder: (context, index) {
                          final entry = _videos[index];
                          return Card(
                            margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            child: ListTile(
                              leading: const CircleAvatar(child: Icon(Icons.video_file)),
                              title: Text(entry.name),
                              subtitle: Text(
                                'Uploadée le ${_formatDate(entry.uploadDate)}',
                                style: const TextStyle(fontSize: 12),
                              ),
                              trailing: _pickMode == null
                                  ? PopupMenuButton<String>(
                                      onSelected: (value) {
                                        if (value == 'rename') _renameVideo(entry);
                                        if (value == 'delete') _deleteVideo(entry);
                                      },
                                      itemBuilder: (context) => [
                                        const PopupMenuItem(
                                          value: 'rename',
                                          child: Row(children: [Icon(Icons.edit), SizedBox(width: 8), Text('Renommer')]),
                                        ),
                                        const PopupMenuItem(
                                          value: 'delete',
                                          child: Row(children: [
                                            Icon(Icons.delete, color: Colors.red),
                                            SizedBox(width: 8),
                                            Text('Supprimer', style: TextStyle(color: Colors.red)),
                                          ]),
                                        ),
                                      ],
                                    )
                                  : const Icon(Icons.arrow_forward_ios, size: 16),
                              onTap: () => _handleVideoTap(entry),
                            ),
                          );
                        },
                      ),
                    ),
                  ],
                ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year} '
        '${date.hour.toString().padLeft(2, '0')}:'
        '${date.minute.toString().padLeft(2, '0')}';
  }
}
