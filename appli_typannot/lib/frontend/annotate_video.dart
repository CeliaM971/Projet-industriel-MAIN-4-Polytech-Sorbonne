import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import 'dart:io';
import 'saved_videos.dart';
import 'server.dart';
import 'group_manager.dart'; // 🔥 IMPORT
import 'dart:convert';
import 'package:http/http.dart' as http;



//Video Loader

class AnnotateVideoLoader extends StatefulWidget {
  final String videoId;

  const AnnotateVideoLoader({Key? key, required this.videoId}) : super(key: key);

  @override
  State<AnnotateVideoLoader> createState() => _AnnotateVideoLoaderState();
}

class _AnnotateVideoLoaderState extends State<AnnotateVideoLoader> {
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _downloadAndOpen();
  }

  Future<void> _downloadAndOpen() async {
    try {
      final serverUrl =
          '${ServerConfig.instance.baseUrl}/videos/${widget.videoId}/download';

      final localFile = await SavedVideosService.instance.downloadVideo(
        widget.videoId,
        serverUrl,
      );

      if (!mounted) return;

      if (localFile == null) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Impossible de télécharger la vidéo';
        });
        return;
      }

      // Remplace la page de chargement par AnnotateVideo
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) => AnnotateVideo(videoPath: localFile.path, videoId: widget.videoId),
        ),
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'Erreur : $e';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Center(
        child: _isLoading
            ? const Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(color: Colors.blue),
                  SizedBox(height: 20),
                  Text(
                    'Chargement de la vidéo...',
                    style: TextStyle(color: Colors.white, fontSize: 16),
                  ),
                ],
              )
            : Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, color: Colors.red, size: 60),
                  const SizedBox(height: 16),
                  Text(
                    _errorMessage ?? 'Erreur inconnue',
                    style: const TextStyle(color: Colors.white),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  ElevatedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Retour'),
                  ),
                ],
              ),
      ),
    );
  }
}

class FrameAnnotation {
  final Duration timestamp;
  final List<List<String>> paths;

  FrameAnnotation({required this.timestamp, required this.paths});

  Map<String, dynamic> toJson() => {
    'timestamp_ms': timestamp.inMilliseconds,
    'paths': paths.asMap().entries.map((e) => {
      'path_order': e.key,
      'path_string': e.value.join('›'),
    }).toList(),
  };
}

class AnnotateVideo extends StatefulWidget {
  final String videoPath;
  final String videoId; // AJOUT
  const AnnotateVideo({Key? key, required this.videoPath, required this.videoId}): super(key: key);

  @override
  State<AnnotateVideo> createState() => _AnnotateVideoState();
}

class _AnnotateVideoState extends State<AnnotateVideo> {
  VideoPlayerController? _controller;
  final GroupManager _groupManager = GroupManager(); // 🔥 INSTANCE
  bool _isVideoInitialized = false;

  // Structure pour gérer les boutons sélectionnés par ligne
  Map<int, String> selectedButtons = {};

  // Liste pour contenir une chaîne d'annotations pour un frame
  List<String> _buildSelectionPath() {
    List<String> path = [];
    int i = 1;
    while (selectedButtons.containsKey(i)) {
      path.add(selectedButtons[i]!);
      i++;
    }
    return path;
  }

  //Liste pour contenir annotations précédentes pour un même frame (quand on change de membre par ex)
  List<List<String>> savedPaths = [];

  //Liste de toutes les annotations pour la vidéo
  final List<FrameAnnotation> _frameAnnotations = [];
  
  // Structure de données pour les boutons conditionnels
  final Map<String, List<String>> buttonTree = {
    'ligne_1': ['Membre sup', 'Doigts', 'Lower Face'],

    'Membre sup': ['Selec G', 'Selec D'],
    'Selec G': ['Epaule', 'Bras','A-Bras','Paume'],
    'Selec D': ['Epaule', 'Bras','A-Bras','Paume'],
    'Epaule':['Flx/Ext','Abd/add','Rot','Up/Down','Forw/back'],
    'Bras':['Flx/Ext','Abd/add','Rot','Up/Down','Forw/back'],
    'A-Bras':['Flx/Ext','Abd/add','Rot','Up/Down','Forw/back'],
    'Paume':['Flx/Ext','Abd/add','Rot','Up/Down','Forw/back'],
    'Flx/Ext':['Flexion','Extension'],
    'Abd/add':['Abduction','Adduction'],
    'Rot':['Rot int','Rot ext'],
    'Up/Down':['Up','Down'],
    'Forw/back':['Forward','Backward'],
    'Flexion':['0/4','1/4','2/4','3/4','4/4'],
    'Extension':['0/4','1/4','2/4','3/4','4/4'],
    'Abduction':['0/4','1/4','2/4','3/4','4/4'],
    'Adduction':['0/4','1/4','2/4','3/4','4/4'],
    'Rot int':['0/4','1/4','2/4','3/4','4/4'],
    'Rot ext':['0/4','1/4','2/4','3/4','4/4'],
    'Up':['0/4','1/4','2/4','3/4','4/4'],
    'Down':['0/4','1/4','2/4','3/4','4/4'],
    'Forward':['0/4','1/4','2/4','3/4','4/4'],
    'Backward':['0/4','1/4','2/4','3/4','4/4'],

    'Doigts': ['Selec G1', 'Selec D1'],
    'Selec G1': ['Phalange 1', 'Phalange 2-3','Pouce','Index','Majeur','Annulaire','Auriculaire'],
    'Selec D1': ['Phalange 1', 'Phalange 2-3','Pouce','Index','Majeur','Annulaire','Auriculaire'],
    'Phalange 1':['Flx/Ext','Abd/add','Rot'],
    'Phalange 2-3':['Flx/Ext','Abd/add','Rot'],
    'Pouce':['Flx/Ext','Abd/add','Rot'],
    'Index':['Flx/Ext','Abd/add','Rot'],
    'Majeur':['Flx/Ext','Abd/add','Rot'],
    'Annulaire':['Flx/Ext','Abd/add','Rot'],
    'Auriculaire':['Flx/Ext','Abd/add','Rot'],
    
    'Lower Face':['Selec G2', 'Selec D2','Selec H', 'Selec B'],
    'Selec G2':['Mâchoire','Lèvres','Coins B','Verm lèvres','Langue','Air'],
    'Selec D2':['Mâchoire','Lèvres','Coins B','Verm lèvres','Langue','Air'],
    'Selec H':['Mâchoire','Lèvres','Coins B','Verm lèvres','Langue','Air'],
    'Selec B':['Mâchoire','Lèvres','Coins B','Verm lèvres','Langue','Air'],
    'Mâchoire':['Gauche/Droite','Up/Down','Forw/back'],
    'Lèvres':['Gauche/Droite','Up/Down','Forw/back'],
    'Coins B':['Gauche/Droite','Up/Down','Forw/back'],
    'Verm lèvres':['Gauche/Droite','Up/Down','Forw/back'],
    'Langue':['Gauche/Droite','Up/Down','Forw/back','Pointé/Plat'],
    'Air':['Inhale/Exhale'],
    'Gauche/Droite':['Gauche','Droite'],
    'Pointé/Plat':['Pointé','Plat'],
    'Inhale/Exhale':['Inhale','Exhale'],
    'Gauche':['0/4','1/4','2/4','3/4','4/4'],
    'Droite':['0/4','1/4','2/4','3/4','4/4'],
    'Pointé':['0/4','1/4','2/4','3/4','4/4'],
    'Plat':['0/4','1/4','2/4','3/4','4/4'],
    'Inhale':['0/4','1/4','2/4','3/4','4/4'],
    'Exhale':['0/4','1/4','2/4','3/4','4/4'],

  };


  Widget _buildSelectionBar() {
    final currentPath = _buildSelectionPath();

    return Container(
      color: Colors.grey[850],
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [

          // --- Chemins sauvegardés ---
          if (savedPaths.isNotEmpty)
            ...savedPaths.asMap().entries.map((entry) {
              final pathIndex = entry.key;
              final path = entry.value;
              return Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Row(
                  children: [
                    Expanded(
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: path.asMap().entries.map((e) {
                            return Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (e.key > 0)
                                  const Icon(Icons.chevron_right,
                                      color: Colors.white24, size: 14),
                                Text(
                                  e.value,
                                  style: const TextStyle(
                                    color: Colors.white54,
                                    fontSize: 12,
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                        ),
                      ),
                    ),
                    // Supprimer ce chemin sauvegardé
                    GestureDetector(
                      onTap: () {
                        setState(() => savedPaths.removeAt(pathIndex));
                      },
                      child: const Padding(
                        padding: EdgeInsets.only(left: 8),
                        child: Icon(Icons.close, color: Colors.red, size: 16),
                      ),
                    ),
                  ],
                ),
              );
            }),

          if (savedPaths.isNotEmpty)
            const Divider(color: Colors.white12, height: 12),

          // --- Chemin en cours ---
          Row(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  reverse: true,
                  child: Row(
                    children: currentPath.isEmpty
                        ? [
                            const Text(
                              'Aucune sélection',
                              style: TextStyle(
                                  color: Colors.white38,
                                  fontSize: 14,
                                  fontStyle: FontStyle.italic),
                            )
                          ]
                        : currentPath.asMap().entries.map((entry) {
                            final index = entry.key;
                            final label = entry.value;
                            return Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (index > 0)
                                  const Icon(Icons.chevron_right,
                                      color: Colors.white38, size: 16),
                                GestureDetector(
                                  onTap: () {
                                    setState(() {
                                      selectedButtons.removeWhere(
                                          (key, _) => key > index + 1);
                                    });
                                  },
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: index == currentPath.length - 1
                                          ? Colors.blue.withOpacity(0.25)
                                          : Colors.transparent,
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(
                                        color: index == currentPath.length - 1
                                            ? Colors.blue
                                            : Colors.transparent,
                                      ),
                                    ),
                                    child: Text(
                                      label,
                                      style: TextStyle(
                                        color: index == currentPath.length - 1
                                            ? Colors.blue
                                            : Colors.white60,
                                        fontSize: 13,
                                        fontWeight:
                                            index == currentPath.length - 1
                                                ? FontWeight.bold
                                                : FontWeight.normal,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          }).toList(),
                  ),
                ),
              ),

              const SizedBox(width: 8),

              // ➕ Valider et ajouter le chemin courant
              if (currentPath.isNotEmpty)
                IconButton(
                  onPressed: () {
                    setState(() {
                      savedPaths.add(List.from(currentPath));
                      selectedButtons.clear(); // repart de zéro
                    });
                  },
                  icon: const Icon(Icons.add_circle, color: Colors.green),
                  tooltip: 'Ajouter cette annotation',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),

              const SizedBox(width: 4),

              // ✕ Effacer chemin courant
              if (currentPath.isNotEmpty)
                IconButton(
                  onPressed: () => setState(() => selectedButtons.clear()),
                  icon: const Icon(Icons.clear_all, color: Colors.red),
                  tooltip: 'Tout effacer',
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                ),

              const SizedBox(width: 4),

              // ⌫ Retour arrière
              IconButton(
                onPressed: currentPath.isEmpty
                    ? null
                    : () => setState(() => selectedButtons.remove(currentPath.length)),
                icon: Icon(Icons.backspace_outlined,
                    color: currentPath.isEmpty ? Colors.white24 : Colors.white70),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
            ],
          ),
        ],
      ),
    );
  }
  
  @override
  void initState() {
    super.initState();
  
  
  // Forcer le mode portrait
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  _initializeVideo();
  _loadExistingAnnotations();
  }

  Future<void> _initializeVideo() async {
    try {
      _controller = VideoPlayerController.file(File(widget.videoPath))
        ..initialize().then((_) {
          setState(() {
            _isVideoInitialized = true;
          });
          _controller!.play();
        });
    } catch (e) {
      print("❌ Erreur lors de l'initialisation de la vidéo: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur lors du chargement de la vidéo: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    // Restaurer toutes les orientations
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    super.dispose();
  }

  // Obtenir les lignes visibles basées sur les sélections
  List<MapEntry<String, List<String>>> getVisibleLines() {
    List<MapEntry<String, List<String>>> lines = [];
    
    // Toujours afficher la première ligne
    lines.add(MapEntry('ligne_1', buttonTree['ligne_1']!));
    
    // Ajouter les lignes suivantes basées sur les sélections
    int lineIndex = 1;
    String? currentKey = selectedButtons[lineIndex];
    
    while (currentKey != null && buttonTree.containsKey(currentKey)) {
      lineIndex++;
      lines.add(MapEntry(currentKey, buttonTree[currentKey]!));
      currentKey = selectedButtons[lineIndex];
    }
    
    return lines;
  }

  void onButtonPressed(int lineIndex, String buttonLabel) {
    setState(() {
      // Si on clique sur le bouton déjà sélectionné, on le désélectionne
      if (selectedButtons[lineIndex] == buttonLabel) {
        selectedButtons.remove(lineIndex);
        // Supprimer toutes les sélections des lignes suivantes
        selectedButtons.removeWhere((key, value) => key > lineIndex);
      } else {
        // Sinon, on sélectionne ce bouton
        selectedButtons[lineIndex] = buttonLabel;
        // Supprimer toutes les sélections des lignes suivantes
        selectedButtons.removeWhere((key, value) => key > lineIndex);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        // 🔥 Afficher le groupe actuel
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: ValueListenableBuilder<Group>(
          valueListenable: _groupManager.currentGroup,
          builder: (context, group, child) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Annotation de vidéo',
                  style: TextStyle(fontSize: 18,color: Colors.white),
                ),
                Text(
                  group.name,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.normal,
                    color: Colors.white70,
                  ),
                ),
              ],
            );
          },
        ),
      ),
      body: Column(
        children: [
          // Partie haute: Vidéo
          Container(
            height: MediaQuery.of(context).size.height * 0.3,
            color: Colors.black,
            child: Stack(
              children: [
                // Vidéo
                Center(
                  child: _isVideoInitialized && _controller != null
                      ? AspectRatio(
                          aspectRatio: _controller!.value.aspectRatio,
                          child: VideoPlayer(_controller!),
                        )
                      : const CircularProgressIndicator(),
                ),

                // Contrôles superposés
                if (_isVideoInitialized && _controller != null)
                  Positioned(
                    bottom: 0, left: 0, right: 0,
                    child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.bottomCenter,
                          end: Alignment.topCenter,
                          colors: [Colors.black87, Colors.transparent],
                        ),
                      ),
                      padding: const EdgeInsets.fromLTRB(12, 16, 12, 4),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          ValueListenableBuilder<VideoPlayerValue>(
                            valueListenable: _controller!,
                            builder: (_, value, __) {
                              final pos = value.position;
                              final dur = value.duration;
                              String fmt(Duration d) =>
                                  '${d.inMinutes.toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';
                              return Column(
                                children: [
                                  VideoProgressIndicator(
                                    _controller!,
                                    allowScrubbing: true,
                                    colors: const VideoProgressColors(
                                      playedColor: Colors.blue,
                                      bufferedColor: Colors.white24,
                                      backgroundColor: Colors.white12,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text(fmt(pos),
                                          style: const TextStyle(color: Colors.white70, fontSize: 11)),
                                      Text(fmt(dur),
                                          style: const TextStyle(color: Colors.white70, fontSize: 11)),
                                    ],
                                  ),
                                ],
                              );
                            },
                          ),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              // ← Frame annoté précédent
                              IconButton(
                                icon: const Icon(Icons.skip_previous, color: Colors.amber, size: 26),
                                onPressed: _gotoPreviousAnnotatedFrame,
                                tooltip: 'Frame annoté précédent',
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                              ),
                              const SizedBox(width: 8),

                              // ← -1s
                              IconButton(
                                icon: const Icon(Icons.chevron_left, color: Colors.white, size: 28),
                                onPressed: _previousFrame,
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                              ),
                              const SizedBox(width: 8),
                              // Play/Pause
                              ValueListenableBuilder<VideoPlayerValue>(
                                valueListenable: _controller!,
                                builder: (_, value, __) => IconButton(
                                  icon: Icon(
                                    value.isPlaying ? Icons.pause_circle_filled : Icons.play_circle_filled,
                                    color: Colors.white, size: 32,
                                  ),
                                  onPressed: () => setState(() {
                                    value.isPlaying ? _controller!.pause() : _controller!.play();
                                  }),
                                  padding: EdgeInsets.zero,
                                  constraints: const BoxConstraints(),
                                ),
                              ),
                              const SizedBox(width: 8),
                              // Replay
                              IconButton(
                                icon: const Icon(Icons.replay, color: Colors.white, size: 26),
                                onPressed: () {
                                  _controller?.seekTo(Duration.zero);
                                  _controller?.play();
                                },
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                              ),
                              const SizedBox(width: 8),
                              // +1s →
                              IconButton(
                                icon: const Icon(Icons.chevron_right, color: Colors.white, size: 28),
                                onPressed: _nextFrame,
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                              ),
                              const SizedBox(width: 8),

                              // Frame annoté suivant →
                              IconButton(
                                icon: const Icon(Icons.skip_next, color: Colors.amber, size: 26),
                                onPressed: _gotoNextAnnotatedFrame,
                                tooltip: 'Frame annoté suivant',
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),

      _buildSelectionBar(),

      // Partie basse : Contenu scrollable avec boutons
          Expanded(
            child: Container(
              color: Colors.grey[900],
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ..._buildButtonLines(),

                    const SizedBox(height: 24),

                    // Boutons d'action
                      Row(
                        children: [
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: () {
                                Navigator.pop(context);
                              },
                              icon: const Icon(Icons.arrow_back),
                              label: const Text('Retour'),
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: ElevatedButton.icon(
                              onPressed: _saveAnnotations,
                              icon: const Icon(Icons.save),
                              label: const Text('Sauvegarder'),
                              style: ElevatedButton.styleFrom(
                                padding: const EdgeInsets.symmetric(vertical: 12),
                                backgroundColor: Colors.green,
                              ),
                            ),
                          ),
                        ],
                      ),


                      const SizedBox(height: 12),
                      if (savedPaths.isNotEmpty)
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: () {
                              if (_controller == null) return;
                              final timestamp = _controller!.value.position;
                              final existing = _frameAnnotations.indexWhere(
                                (f) => (f.timestamp - timestamp).abs() < const Duration(milliseconds: 200),
                              );
                              setState(() {
                                if (existing >= 0) {
                                  _frameAnnotations[existing] = FrameAnnotation(
                                    timestamp: _frameAnnotations[existing].timestamp,
                                    paths: [..._frameAnnotations[existing].paths, ...savedPaths],
                                  );
                                } else {
                                  _frameAnnotations.add(FrameAnnotation(
                                    timestamp: timestamp,
                                    paths: List.from(savedPaths),
                                  ));
                                  _frameAnnotations.sort((a, b) => a.timestamp.compareTo(b.timestamp));
                                }
                                savedPaths.clear();
                                selectedButtons.clear();
                              });
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Annotations enregistrées à ${_formatDuration(timestamp)}'),
                                  backgroundColor: Colors.green[700],
                                  duration: const Duration(seconds: 2),
                                ),
                              );
                            },
                            icon: const Icon(Icons.bookmark_add),
                            label: const Text('Enregistrer pour ce frame'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.green[700],
                              padding: const EdgeInsets.symmetric(vertical: 14),
                            ),
                          ),
                        ),


                        const SizedBox(height: 24),

                        // Récapitulatif de toutes les annotations
                        if (_frameAnnotations.isNotEmpty) _buildFrameAnnotationsSummary(),

                        const SizedBox(height: 16),
                        
                    ],
                  ), 
                ),
              ),
            ),
          ],
        ),
      );
    }


  List<Widget> _buildButtonLines() {
    List<Widget> widgets = [];
    var visibleLines = getVisibleLines();
    
    for (int i = 0; i < visibleLines.length; i++) {
      var entry = visibleLines[i];
      int lineIndex = i + 1;
      
      widgets.add(
        Padding(
          padding: const EdgeInsets.only(bottom: 24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Ligne $lineIndex',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              // Scroll horizontal pour les boutons avec effet carousel
              SizedBox(
                height: 60, // Hauteur fixe pour la ligne de boutons
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: entry.value.map((buttonLabel) {
                      bool isSelected = selectedButtons[lineIndex] == buttonLabel;
                      
                      return Padding(
                        padding: const EdgeInsets.only(right: 12.0),
                        child: GestureDetector(
                          onTap: () => onButtonPressed(lineIndex, buttonLabel),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 24,
                              vertical: 16,
                            ),
                            decoration: BoxDecoration(
                              color: isSelected
                                  ? Colors.blue.withOpacity(0.2)
                                  : Colors.grey[800],
                              border: Border.all(
                                color: isSelected ? Colors.blue : Colors.grey[700]!,
                                width: isSelected ? 3 : 1,
                              ),
                              borderRadius: BorderRadius.circular(12),
                              boxShadow: isSelected
                                  ? [
                                      BoxShadow(
                                        color: Colors.blue.withOpacity(0.5),
                                        blurRadius: 8,
                                        spreadRadius: 2,
                                      )
                                    ]
                                  : null,
                            ),
                            child: Center(
                              child: Text(
                                buttonLabel,
                                style: TextStyle(
                                  color: isSelected ? Colors.blue : Colors.white,
                                  fontSize: 16,
                                  fontWeight:
                                      isSelected ? FontWeight.bold : FontWeight.normal,
                                ),
                              ),
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }
    
    return widgets;
  }

  Widget _buildFrameAnnotationsSummary() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.grey[850],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white12),
      ),
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.list_alt, color: Colors.white70, size: 16),
              const SizedBox(width: 8),
              Text(
                '${_frameAnnotations.length} frame(s) annoté(s)',
                style: const TextStyle(
                  color: Colors.white70,
                  fontSize: 13,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ..._frameAnnotations.asMap().entries.map((entry) {
            final i = entry.key;
            final fa = entry.value;
            return Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.grey[800],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.access_time, color: Colors.blue, size: 14),
                      const SizedBox(width: 6),
                      Text(
                        _formatDuration(fa.timestamp),
                        style: const TextStyle(
                          color: Colors.blue,
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        ),
                      ),
                      const Spacer(),
                      // Aller à ce timestamp
                      GestureDetector(
                        onTap: () {
                          _controller?.seekTo(fa.timestamp);
                          _controller?.pause();
                        },
                        child: const Icon(Icons.play_circle_outline,
                            color: Colors.white54, size: 18),
                      ),
                      const SizedBox(width: 10),
                      // Supprimer ce frame
                      GestureDetector(
                        onTap: () => setState(() => _frameAnnotations.removeAt(i)),
                        child: const Icon(Icons.delete_outline,
                            color: Colors.red, size: 18),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  ...fa.paths.asMap().entries.map((pathEntry) {
                    final pathIndex = pathEntry.key;
                    final path = pathEntry.value;
                    return Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Row(
                        children: [
                          const Icon(Icons.chevron_right, color: Colors.white24, size: 14),
                          const SizedBox(width: 4),
                          Expanded(
                            child: Text(
                              path.join(' › '),
                              style: const TextStyle(color: Colors.white60, fontSize: 12),
                            ),
                          ),
                          GestureDetector(
                            onTap: () => setState(() {
                              final updatedPaths = List<List<String>>.from(fa.paths)
                                ..removeAt(pathIndex);

                              if (updatedPaths.isEmpty) {
                                // Plus aucune annotation : on supprime le timestamp entier
                                _frameAnnotations.removeAt(i);
                              } else {
                                _frameAnnotations[i] = FrameAnnotation(
                                  timestamp: fa.timestamp,
                                  paths: updatedPaths,
                                );
                              }
                            }),
                            child: const Padding(
                              padding: EdgeInsets.only(left: 8),
                              child: Icon(Icons.remove_circle_outline, color: Colors.red, size: 14),
                            ),
                          ),
                        ],
                      ),
                    );
                  }),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  String _formatDuration(Duration d) {
    final min = d.inMinutes.toString().padLeft(2, '0');
    final sec = (d.inSeconds % 60).toString().padLeft(2, '0');
    final ms  = (d.inMilliseconds % 1000 ~/ 10).toString().padLeft(2, '0');
    return '$min:$sec.$ms';
  }

  //Méthodes de navigation dans la vidéo

  Future<void> _previousFrame() async {
    if (_controller == null) return;
    await _controller!.pause();
    final pos = _controller!.value.position - const Duration(seconds: 1);
    await _controller!.seekTo(pos < Duration.zero ? Duration.zero : pos);
    setState(() {});
  }

  Future<void> _nextFrame() async {
    if (_controller == null) return;
    await _controller!.pause();
    final pos = _controller!.value.position + const Duration(seconds: 1);
    final max = _controller!.value.duration;
    await _controller!.seekTo(pos > max ? max : pos);
    setState(() {});
  }


  Future<void> _gotoPreviousAnnotatedFrame() async {
    if (_controller == null || _frameAnnotations.isEmpty) return;
    final current = _controller!.value.position;

    // Cherche le dernier timestamp strictement avant la position actuelle
    final previous = _frameAnnotations
        .where((f) => f.timestamp < current - const Duration(milliseconds: 200))
        .lastOrNull;

    if (previous != null) {
      await _controller!.pause();
      await _controller!.seekTo(previous.timestamp);
      setState(() {});
    }
  }

  Future<void> _gotoNextAnnotatedFrame() async {
    if (_controller == null || _frameAnnotations.isEmpty) return;
    final current = _controller!.value.position;

    // Cherche le premier timestamp strictement après la position actuelle
    final next = _frameAnnotations
        .where((f) => f.timestamp > current + const Duration(milliseconds: 200))
        .firstOrNull;

    if (next != null) {
      await _controller!.pause();
      await _controller!.seekTo(next.timestamp);
      setState(() {});
    }
  }


Future<void> _saveAnnotations() async {
  if (_frameAnnotations.isEmpty) return;

  final server = ServerConfig.instance;

  final payload = jsonEncode({
    'video_id': int.parse(widget.videoId),
    'annotations': _frameAnnotations.map((f) => f.toJson()).toList(),
  });

  try {
    final response = await http.post(
      Uri.parse('${server.baseUrl}/annotations/videos/${widget.videoId}/annotations/bulk'),
      headers: {
        ...server.authHeaders(),
        'Content-Type': 'application/json',
      },
      body: payload,
    );

    if (response.statusCode == 201) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('✅ Annotations sauvegardées'),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.pushNamedAndRemoveUntil(context, '/', (route) => false);
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('❌ Erreur: ${response.statusCode} - ${response.body}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  } catch (e) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('❌ Erreur réseau: $e'),
          backgroundColor: Colors.red,
        ),
      );
    }
  }
}

Future<void> _loadExistingAnnotations() async {
  final server = ServerConfig.instance;
  try {
    final response = await http.get(
      Uri.parse('${server.baseUrl}/annotations/videos/${widget.videoId}/annotations'),
      headers: server.authHeaders(),
    );

    if (response.statusCode == 200) {
      final List data = jsonDecode(response.body);
      setState(() {
        for (final ann in data) {
          final timestamp = Duration(milliseconds: ann['timestamp_ms']);
          final List pathsList = ann['paths'];
          final paths = pathsList.map<List<String>>((p) {
            return (p['path_string'] as String).split('›');
          }).toList();

          // Éviter les doublons si déjà en mémoire
          final exists = _frameAnnotations.any(
            (f) => (f.timestamp - timestamp).abs() < const Duration(milliseconds: 100),
          );
          if (!exists) {
            _frameAnnotations.add(FrameAnnotation(timestamp: timestamp, paths: paths));
          }
        }
        _frameAnnotations.sort((a, b) => a.timestamp.compareTo(b.timestamp));
      });
    }
  } catch (e) {
    print('Erreur chargement annotations: $e');
  }
}



}