import 'dart:io';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'saved_videos.dart';
import 'group_manager.dart';

class SavedVideosListScreen extends StatefulWidget {
  const SavedVideosListScreen({super.key});

  @override
  State<SavedVideosListScreen> createState() => _SavedVideosListScreenState();
}

class _SavedVideosListScreenState extends State<SavedVideosListScreen> {
  List<SavedVideoEntry> _videos = [];
  bool _isLoading = true;
  final GroupManager _groupManager = GroupManager();

  @override
  void initState() {
    super.initState();
    _loadVideos();
    
    // Listen to the group changes
    _groupManager.currentGroup.addListener(_onGroupChanged);
  }

  @override
  void dispose() {
    _groupManager.currentGroup.removeListener(_onGroupChanged);
    super.dispose();
  }

  void _onGroupChanged() {
    print("🔄 Groupe changé, rechargement des vidéos...");
    _loadVideos();
  }

  // Update method
  Future<void> _loadVideos() async {
    setState(() => _isLoading = true);

    final currentGroup = _groupManager.currentGroup.value;
    
    print("Chargement des vidéos pour le groupe: ${currentGroup.name} (ID: ${currentGroup.id})");

    if (currentGroup.id == 0) {
      // Groupe par défaut non sélectionné
      print("Aucun groupe sélectionné");
      setState(() {
        _videos = [];
        _isLoading = false;
      });
      return;
    }

    final videosFromServer = await SavedVideosService.instance.fetchGroupVideos(currentGroup.id);

    setState(() {
      _videos = videosFromServer;
      _isLoading = false;
    });
    
    print("${_videos.length} vidéos chargées");
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        // Afficher le groupe actuel dans l'AppBar
        title: ValueListenableBuilder<Group>(
          valueListenable: _groupManager.currentGroup,
          builder: (context, group, child) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Mes vidéos sauvegardées',
                  style: TextStyle(fontSize: 18),
                ),
                Text(
                  group.name,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.normal,
                  ),
                ),
              ],
            );
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadVideos,
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
                      // Message dynamique selon le groupe
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
                      // Bouton pour aller à la sélection de groupe
                      ElevatedButton.icon(
                        onPressed: () {
                          Navigator.pushNamed(context, '/group_selection');
                        },
                        icon: const Icon(Icons.group),
                        label: const Text('Choisir un groupe'),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _videos.length,
                  itemBuilder: (context, index) {
                    final video = _videos[index];
                    return Card(
                      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                      child: ListTile(
                        leading: const Icon(Icons.video_file, size: 40),
                        title: Text(video.name),
                        subtitle: Text(
                          'Uploadée le ${_formatDate(video.uploadDate)}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              icon: const Icon(Icons.play_circle_outline),
                              onPressed: () => _playVideo(video),
                            ),
                            IconButton(
                              icon: const Icon(Icons.edit),
                              onPressed: () => _renameVideo(video),
                            ),
                            IconButton(
                              icon: const Icon(Icons.delete, color: Colors.red),
                              onPressed: () => _deleteVideo(video),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
  }

  Future<void> _playVideo(SavedVideoEntry video) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(child: CircularProgressIndicator()),
    );

    final localFile = await SavedVideosService.instance.downloadVideo(
      video.videoId,
      video.serverUrl,
    );

    if (!mounted) return;
    Navigator.pop(context);

    if (localFile == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Erreur lors du téléchargement')),
      );
      return;
    }

    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => VideoViewerScreen(videoFile: localFile),
      ),
    );
  }

  Future<void> _renameVideo(SavedVideoEntry video) async {
    final controller = TextEditingController(text: video.name);
    
    final newName = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Renommer la vidéo'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Nouveau nom'),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Renommer'),
          ),
        ],
      ),
    );

    if (newName != null && newName.isNotEmpty) {
      await SavedVideosService.instance.renameVideo(video.videoId, newName);
      await _loadVideos();
    }
  }

  Future<void> _deleteVideo(SavedVideoEntry video) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Supprimer la vidéo'),
        content: Text('Voulez-vous vraiment supprimer "${video.name}" ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Annuler'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Supprimer'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      await SavedVideosService.instance.deleteVideo(video.videoId);
      _loadVideos();
    }
  }
}

class VideoViewerScreen extends StatefulWidget {
  final File videoFile;

  const VideoViewerScreen({super.key, required this.videoFile});

  @override
  State<VideoViewerScreen> createState() => _VideoViewerScreenState();
}

class _VideoViewerScreenState extends State<VideoViewerScreen> {
  late VideoPlayerController _controller;

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.file(widget.videoFile)
      ..initialize().then((_) {
        setState(() {});
        _controller.play();
      });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Lecture vidéo')),
      body: Center(
        child: _controller.value.isInitialized
            ? Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  AspectRatio(
                    aspectRatio: _controller.value.aspectRatio,
                    child: VideoPlayer(_controller),
                  ),
                  const SizedBox(height: 20),
                  IconButton(
                    icon: Icon(
                      _controller.value.isPlaying ? Icons.pause : Icons.play_arrow,
                      size: 50,
                    ),
                    onPressed: () {
                      setState(() {
                        _controller.value.isPlaying
                            ? _controller.pause()
                            : _controller.play();
                      });
                    },
                  ),
                ],
              )
            : const CircularProgressIndicator(),
      ),
    );
  }
}
