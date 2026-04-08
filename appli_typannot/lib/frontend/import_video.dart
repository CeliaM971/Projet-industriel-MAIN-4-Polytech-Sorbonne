import 'dart:io';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:ffmpeg_kit_flutter_new/ffmpeg_kit.dart';
import 'package:ffmpeg_kit_flutter_new/return_code.dart';
import 'saved_videos.dart';
import 'group_manager.dart'; 

class VideoPlayerScreen extends StatefulWidget {
  const VideoPlayerScreen({super.key});

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  VideoPlayerController? _controller;
  File? _videoFile;
  SavedVideoEntry? _savedVideoEntry; // Stocker l'entrée après sauvegarde

  Rect? _cropRect;
  
  bool _isSaving = false;
  final GroupManager _groupManager = GroupManager(); // INSTANCE

  // MÉTHODE MISE À JOUR
  Future<void> _saveVideo() async {
    if (_videoFile == null) return;

    // Vérifier qu'un groupe est sélectionné
    final currentGroup = _groupManager.currentGroup.value;
    if (currentGroup.id == 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Veuillez sélectionner un groupe avant d\'enregistrer'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }

    setState(() => _isSaving = true);
    try {
      // Appel modifié pour utiliser sendToBackend avec le groupId
      final uploadResult = await sendToBackend(
        _videoFile!.path,
        groupId: currentGroup.id, // Passer le groupId
      );

      if (uploadResult == null) {
        throw Exception("Échec de l'upload");
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('✅ Vidéo enregistrée dans "${currentGroup.name}"'),
          backgroundColor: Colors.green,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('❌ Erreur lors de l\'enregistrement: $e'),
          backgroundColor: Colors.red,
        ),
      );
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }

  Future<void> _pickVideo() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(
      type: FileType.video,
    );

    if (result != null && result.files.single.path != null) {
      final file = File(result.files.single.path!);
      _videoFile = file;

      _controller = VideoPlayerController.file(file)
        ..initialize().then((_) {
          setState(() {});
          _controller!.play();
          _controller!.setLooping(true);
        });
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
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
                  'Importer une vidéo',
                  style: TextStyle(fontSize: 18),
                ),
                Text(
                  group.id == 0 ? 'Aucun groupe sélectionné' : group.name,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.normal,
                    color: group.id == 0 ? Colors.orange : Colors.white70,
                  ),
                ),
              ],
            );
          },
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // NOUVEAU : Card pour afficher le groupe actuel
            ValueListenableBuilder<Group>(
              valueListenable: _groupManager.currentGroup,
              builder: (context, group, child) {
                return Card(
                  color: group.id == 0 ? Colors.orange[50] : Colors.green[50],
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Row(
                      children: [
                        Icon(
                          group.id == 0 ? Icons.warning : Icons.check_circle,
                          color: group.id == 0 ? Colors.orange : Colors.green,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                group.id == 0
                                    ? 'Aucun groupe sélectionné'
                                    : 'Groupe actuel : ${group.name}',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: group.id == 0 ? Colors.orange[900] : Colors.green[900],
                                ),
                              ),
                              if (group.id == 0)
                                const Text(
                                  'Sélectionnez un groupe pour enregistrer la vidéo',
                                  style: TextStyle(fontSize: 12, color: Colors.black54),
                                ),
                            ],
                          ),
                        ),
                        if (group.id == 0)
                          IconButton(
                            icon: const Icon(Icons.group),
                            onPressed: () {
                              Navigator.pushNamed(context, '/group_selection');
                            },
                            tooltip: 'Choisir un groupe',
                          ),
                      ],
                    ),
                  ),
                );
              },
            ),
            
            const SizedBox(height: 16),
            
            ElevatedButton.icon(
              onPressed: _pickVideo,
              icon: const Icon(Icons.video_library),
              label: const Text('Importer une vidéo'),
              style: ElevatedButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
              ),
            ),
            
            const SizedBox(height: 20),
            
            Expanded(
              child: _controller == null
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.video_file,
                            size: 80,
                            color: Colors.grey[400],
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Aucune vidéo sélectionnée',
                            style: TextStyle(
                              fontSize: 16,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    )
                  : Center(
                      child: AspectRatio(
                        aspectRatio: _controller!.value.aspectRatio,
                        child: VideoPlayer(_controller!),
                      ),
                    ),
            ),
            
            const SizedBox(height: 20),
            
            if (_controller != null)
              ElevatedButton.icon(
                onPressed: () {
                  setState(() {
                    if (_controller!.value.isPlaying) {
                      _controller!.pause();
                    } else {
                      _controller!.play();
                    }
                  });
                },
                icon: Icon(
                  _controller!.value.isPlaying ? Icons.pause : Icons.play_arrow,
                ),
                label: Text(
                  _controller!.value.isPlaying ? 'Pause' : 'Play',
                ),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
                ),
              ),
            
            const SizedBox(height: 20),
            
            if (_controller != null)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: () async {
                    final croppedVideoPath = await Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (context) => VideoCropScreen(
                          videoFile: _videoFile!,
                          controller: _controller!,
                        ),
                      ),
                    );
                    
                    if (croppedVideoPath != null) {
                      if (croppedVideoPath is Map<String, dynamic>) {
                        final path = croppedVideoPath['path'] as String;
                        _cropRect = croppedVideoPath['cropRect'] as Rect;
                        
                        _controller?.dispose();
                        final croppedFile = File(path);
                        _videoFile = croppedFile;
                        _savedVideoEntry = null;
                        
                        _controller = VideoPlayerController.file(croppedFile)
                          ..initialize().then((_) {
                            setState(() {});
                            _controller!.play();
                            _controller!.setLooping(true);
                          });
                      }
                    }
                  },
                  icon: const Icon(Icons.crop),
                  label: const Text('Rogner la vidéo'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                    backgroundColor: Colors.orange,
                  ),
                ),
              ),
            
            const SizedBox(height: 10),
            
            if (_controller != null)
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _isSaving ? null : _saveVideo,
                  icon: _isSaving
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save),
                  label: const Text('Enregistrer la vidéo'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                ),
              ),

            const SizedBox(height: 12),
            
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _controller == null
                    ? null
                    : () {
                        Navigator.pushNamed(
                          context,
                          '/analysis',
                          arguments: {
                            'videoPath': _videoFile!.path,
                            'videoId': int.parse(_savedVideoEntry!.videoId),
                            'cropRect': _cropRect,
                          },
                        );
                      },
                child: const Text('Continuer vers l\'analyse'),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class VideoCropScreen extends StatefulWidget {
  final File videoFile;
  final VideoPlayerController controller;

  const VideoCropScreen({
    super.key,
    required this.videoFile,
    required this.controller,
  });

  @override
  State<VideoCropScreen> createState() => _VideoCropScreenState();
}

class _VideoCropScreenState extends State<VideoCropScreen> {
  Rect _cropRect = const Rect.fromLTWH(0, 0, 1, 1);
  bool _isProcessing = false;
  double _progress = 0.0;

  @override
  Widget build(BuildContext context) {
    final videoSize = widget.controller.value.size;
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rogner la vidéo'),
        actions: [
          if (!_isProcessing)
            IconButton(
              icon: const Icon(Icons.check),
              onPressed: _cropVideo,
              tooltip: 'Valider le rognage',
            ),
        ],
      ),
      body: _isProcessing
          ? Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const CircularProgressIndicator(),
                  const SizedBox(height: 20),
                  Text(
                    'Traitement en cours...',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '${(_progress * 100).toStringAsFixed(0)}%',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ],
              ),
            )
          : Column(
              children: [
                Expanded(
                  child: Center(
                    child: AspectRatio(
                      aspectRatio: widget.controller.value.aspectRatio,
                      child: Stack(
                        children: [
                          VideoPlayer(widget.controller),
                          Positioned.fill(
                            child: CustomPaint(
                              painter: CropOverlayPainter(_cropRect),
                            ),
                          ),
                          Positioned.fill(
                            child: GestureDetector(
                              onPanUpdate: (details) {
                                setState(() {
                                  final RenderBox box = context.findRenderObject() as RenderBox;
                                  final localPosition = box.globalToLocal(details.globalPosition);
                                  final size = box.size;
                                  
                                  double x = (localPosition.dx / size.width).clamp(0.0, 1.0);
                                  double y = (localPosition.dy / size.height).clamp(0.0, 1.0);
                                  
                                  _cropRect = Rect.fromLTWH(
                                    (_cropRect.left + x - _cropRect.center.dx).clamp(0.0, 1.0 - _cropRect.width),
                                    (_cropRect.top + y - _cropRect.center.dy).clamp(0.0, 1.0 - _cropRect.height),
                                    _cropRect.width,
                                    _cropRect.height,
                                  );
                                });
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.black87,
                  child: Column(
                    children: [
                      const Text(
                        'Ajustez la zone de rognage',
                        style: TextStyle(color: Colors.white, fontSize: 16),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          const Text('Largeur:', style: TextStyle(color: Colors.white)),
                          Expanded(
                            child: Slider(
                              value: _cropRect.width,
                              min: 0.1,
                              max: 1.0,
                              onChanged: (value) {
                                setState(() {
                                  _cropRect = Rect.fromLTWH(
                                    _cropRect.left.clamp(0.0, 1.0 - value),
                                    _cropRect.top,
                                    value,
                                    _cropRect.height,
                                  );
                                });
                              },
                            ),
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          const Text('Hauteur:', style: TextStyle(color: Colors.white)),
                          Expanded(
                            child: Slider(
                              value: _cropRect.height,
                              min: 0.1,
                              max: 1.0,
                              onChanged: (value) {
                                setState(() {
                                  _cropRect = Rect.fromLTWH(
                                    _cropRect.left,
                                    _cropRect.top.clamp(0.0, 1.0 - value),
                                    _cropRect.width,
                                    value,
                                  );
                                });
                              },
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Future<void> _cropVideo() async {
    setState(() {
      _isProcessing = true;
      _progress = 0.0;
    });

    try {
      final videoSize = widget.controller.value.size;
      
      final int x = (_cropRect.left * videoSize.width).round();
      final int y = (_cropRect.top * videoSize.height).round();
      final int width = (_cropRect.width * videoSize.width).round();
      final int height = (_cropRect.height * videoSize.height).round();

      final int evenWidth = width % 2 == 0 ? width : width - 1;
      final int evenHeight = height % 2 == 0 ? height : height - 1;

      final directory = await getApplicationDocumentsDirectory();
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final outputPath = '${directory.path}/cropped_video_$timestamp.mp4';

      final command = '-i ${widget.videoFile.path} -vf "crop=$evenWidth:$evenHeight:$x:$y" -c:a copy $outputPath';

      await FFmpegKit.execute(command).then((session) async {
        final returnCode = await session.getReturnCode();
        
        if (ReturnCode.isSuccess(returnCode)) {
          setState(() {
            _progress = 1.0;
          });

          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('Vidéo rognée avec succès !'),
                backgroundColor: Colors.green,
              ),
            );

            Navigator.pop(context, outputPath);
          }
        } else {
          throw Exception('Erreur lors du rognage');
        }
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erreur: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isProcessing = false;
        });
      }
    }
  }
}

class CropOverlayPainter extends CustomPainter {
  final Rect cropRect;

  CropOverlayPainter(this.cropRect);

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.black.withOpacity(0.5)
      ..style = PaintingStyle.fill;

    final cropRectPixels = Rect.fromLTWH(
      cropRect.left * size.width,
      cropRect.top * size.height,
      cropRect.width * size.width,
      cropRect.height * size.height,
    );

    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width, cropRectPixels.top),
      paint,
    );

    canvas.drawRect(
      Rect.fromLTWH(0, cropRectPixels.bottom, size.width, size.height - cropRectPixels.bottom),
      paint,
    );

    canvas.drawRect(
      Rect.fromLTWH(0, cropRectPixels.top, cropRectPixels.left, cropRectPixels.height),
      paint,
    );

    canvas.drawRect(
      Rect.fromLTWH(cropRectPixels.right, cropRectPixels.top, size.width - cropRectPixels.right, cropRectPixels.height),
      paint,
    );

    final borderPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.0;

    canvas.drawRect(cropRectPixels, borderPaint);

    final handlePaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;

    final handleSize = 12.0;
    canvas.drawCircle(cropRectPixels.topLeft, handleSize / 2, handlePaint);
    canvas.drawCircle(cropRectPixels.topRight, handleSize / 2, handlePaint);
    canvas.drawCircle(cropRectPixels.bottomLeft, handleSize / 2, handlePaint);
    canvas.drawCircle(cropRectPixels.bottomRight, handleSize / 2, handlePaint);
  }

  @override
  bool shouldRepaint(CropOverlayPainter oldDelegate) {
    return oldDelegate.cropRect != cropRect;
  }
}
