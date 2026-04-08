import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'server.dart';
import 'saved_videos.dart';
import '../MediaPipe/mediapipe_service.dart';
import '../MediaPipe/mocap_gui1.dart';
import 'plotting.dart';
import '../MediaPipe/constants.dart';

class Analysis extends StatefulWidget {
  final String videoId; // ID de la vidéo sur le serveur (pour AlphaPose, MMPose, 6DRepNet)
  //final HolisticVideoResult? holisticResults;
  final Rect? cropRect;

  const Analysis({
    super.key, 
    //this.holisticResults, 
    required this.videoId,
    this.cropRect,
  });

  factory Analysis.fromArguments(Map<String, dynamic> args) {
    return Analysis(
      videoId: args['videoId'],
      //holisticResults: args['holisticResults'] as HolisticVideoResult?,
      cropRect: args['cropRect'],
    );
  }

  @override
  State<Analysis> createState() => _AnalysisState();
}

class _AnalysisState extends State<Analysis> {

  File? _localVideoFile;

  //Vidéo principale
  late VideoPlayerController _videoController;
  ChewieController? _chewieController;
  bool _isLoading = true;

  // Etat analyse
  bool _isProcessing = false; // Pour MediaPipe : extraction des keypoints
  bool _isAnalyzing = false;
  String _analysisProgress = ''; // Pour l'analyse finale
  

  //Résultats MediaPipe
  HolisticVideoResult? _holisticResults;
  MotionData? _currentMotionData;
  MotionType? _currentMotionType;

  // Résultats serveur
  VideoPlayerController? _skeletonVideoController;
  ChewieController? _skeletonChewieController;
  bool _isLoadingSkeletonVideo = false;
  String? _lastResultFileName;
  MotionData? _serverMotionData;
  MotionType? _serverMotionType;

  // Sélections
  String _selectedModel = 'AlphaPose';
  String _selectedLimb = 'Head';
  String _selectedAction = 'Abduction/Adduction';
  bool _isLateral = false;
  bool _deleteLastSlices = false;
  bool _includeLimitOfData = true;

  // Contrôleurs
  final _startTimeCtrl = TextEditingController(text: '0');
  final _endTimeCtrl = TextEditingController(text: '5');
  final _frameRateCtrl = TextEditingController(text: '24');
  final _thresholdMinCtrl = TextEditingController();
  final _thresholdMaxCtrl = TextEditingController();
  final _zoomStartCtrl = TextEditingController();
  final _zoomEndCtrl = TextEditingController();
  final _limitMinCtrl = TextEditingController();
  final _limitMaxCtrl = TextEditingController();

  final MocapController _mocapController = MocapController();
  final server = ServerConfig.instance;

  @override
  void initState() {
    super.initState();
    //_holisticResults = widget.holisticResults;
    _initVideo();
  }
  

  Future<void> _initVideo() async {

    setState(() => _isLoading = true);

    try {

        final localFile = await SavedVideosService.instance.downloadVideo(
        widget.videoId,
        '${server.baseUrl}/videos/${widget.videoId}/download',
      );

      if (localFile != null) {
        
        _localVideoFile = localFile; 
        _videoController = VideoPlayerController.file(localFile);  // ← MANQUANT
        await _videoController.initialize(); 
        _chewieController = ChewieController(
          videoPlayerController: _videoController,
          autoPlay: false,
          looping: false,
          showControls: false,
          materialProgressColors: ChewieProgressColors(
            playedColor: const Color(0xFF8B6F5C),
            handleColor: const Color(0xFF8B6F5C),
          ),
        );

        _endTimeCtrl.text = _videoController.value.duration.inSeconds.toString();
      }
    } catch (e) {
      print('Erreur initVideo: $e');
    } finally {
      setState(() => _isLoading = false);
    }
  }

  @override
  void dispose() {
    _videoController.dispose();
    _chewieController?.dispose();
    _skeletonVideoController?.dispose();
    _skeletonChewieController?.dispose();
    _startTimeCtrl.dispose();
    _endTimeCtrl.dispose();
    _frameRateCtrl.dispose();
    _thresholdMinCtrl.dispose();
    _thresholdMaxCtrl.dispose();
    _zoomStartCtrl.dispose();
    _zoomEndCtrl.dispose();
    _limitMinCtrl.dispose();
    _limitMaxCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAF9F6),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF5C4033)),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text(
          'Analyse',
          style: TextStyle(
            color: Color(0xFF5C4033),
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      body: Stack(
        children: [
          // Vidéo
          Column (
            children: [
              AspectRatio(
                aspectRatio: 16 / 9,
                child: Stack(
                  children: [
                    // Vidéo en fond
                    Container(
                      color: Colors.black,
                      child: _isLoading
                          ? const Center(child: CircularProgressIndicator())
                          : (_chewieController != null
                              ? Chewie(controller: _chewieController!)
                              : const Center(child: Text('Erreur',
                                  style: TextStyle(color: Colors.white)))),
                    ),

                    // Contrôles superposés en bas
                    if (!_isLoading && _chewieController != null)
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
                          padding: const EdgeInsets.fromLTRB(12, 16, 12, 6),
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              // Timer + barre de progression
                              ValueListenableBuilder<VideoPlayerValue>(
                                valueListenable: _videoController,
                                builder: (_, value, __) {
                                  final pos = value.position;
                                  final dur = value.duration;
                                  String fmt(Duration d) =>
                                      '${d.inMinutes.toString().padLeft(2, '0')}:${(d.inSeconds % 60).toString().padLeft(2, '0')}';
                                  return Column(
                                    children: [
                                      VideoProgressIndicator(
                                        _videoController,
                                        allowScrubbing: true,
                                        colors: const VideoProgressColors(
                                          playedColor: Color(0xFF8B6F5C),
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
                              // Boutons
                              Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  IconButton(
                                    onPressed: _previousFrame,
                                    icon: const Icon(Icons.chevron_left, color: Colors.white, size: 28),
                                    padding: EdgeInsets.zero,
                                    constraints: const BoxConstraints(),
                                  ),
                                  const SizedBox(width: 12),
                                  ValueListenableBuilder<VideoPlayerValue>(
                                    valueListenable: _videoController,
                                    builder: (_, value, __) => IconButton(
                                      onPressed: () => setState(() {
                                        value.isPlaying
                                            ? _videoController.pause()
                                            : _videoController.play();
                                      }),
                                      icon: Icon(
                                        value.isPlaying
                                            ? Icons.pause_circle_filled
                                            : Icons.play_circle_filled,
                                        color: Colors.white,
                                        size: 32,
                                      ),
                                      padding: EdgeInsets.zero,
                                      constraints: const BoxConstraints(),
                                    ),
                                  ),
                                  const SizedBox(width: 12),
                                  IconButton(
                                    onPressed: _nextFrame,
                                    icon: const Icon(Icons.chevron_right, color: Colors.white, size: 28),
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

              // Formulaire d'analyse
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [

                      _buildSection('Modèle', Icons.architecture_rounded, [
                                _buildRadio('MediaPipe'),
                                _buildRadio('AlphaPose'),
                                _buildRadio('MMPose'),
                                _buildRadio('6DRepNet'),
                      ]),
                      
                      const SizedBox(height: 16),

                      _buildSection('Options', Icons.settings_rounded, [
                        _buildSwitch('Delete Last Slices', _deleteLastSlices, 
                          (v) => setState(() => _deleteLastSlices = v)),
                        _buildSwitch('Include Limit of Data', _includeLimitOfData, 
                          (v) => setState(() => _includeLimitOfData = v)),
                      ]),
              
                      _buildSection('Membre', Icons.accessibility_new_rounded, [
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _buildChip('Head'),
                            _buildChip('Shoulder'),
                            _buildChip('Torso'),
                            _buildChip('Arm'),
                            _buildChip('Fore Arm'),
                          ],
                        ),
                      ]),
                      
                      _buildSection('Action', Icons.motion_photos_on_rounded, [
                        _buildActionBtn('Abduction/Adduction'),
                        const SizedBox(height: 8),
                        _buildActionBtn('Flexion/Extension'),
                        const SizedBox(height: 8),
                        _buildActionBtn('Rotation'),

                        //Checkbox latéral (seulement pour Tête et Bras + MediaPipe POUR L'INSTANT)
                        if (_shouldShowLateralOption())
                          CheckboxListTile(title: const Text('Latéral'),
                                          value: _isLateral, 
                                          onChanged: (v) => setState(() => _isLateral = v ?? false),
                                          ),
                      ]),
                      
                      _buildSection('Paramètres', Icons.tune_rounded, [
                        Row(
                          children: [
                            Expanded(child: _buildField('Start (s)', _startTimeCtrl)),
                            const SizedBox(width: 12),
                            Expanded(child: _buildField('End (s)', _endTimeCtrl)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(child: _buildField('Threshold min', _thresholdMinCtrl)),
                            const SizedBox(width: 12),
                            Expanded(child: _buildField('Threshold max', _thresholdMaxCtrl)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(child: _buildField('Zoom Start', _zoomStartCtrl)),
                            const SizedBox(width: 12),
                            Expanded(child: _buildField('Zoom End', _zoomEndCtrl)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(child: _buildField('Limit min', _limitMinCtrl)),
                            const SizedBox(width: 12),
                            Expanded(child: _buildField('Limit max', _limitMaxCtrl)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        _buildField('Frame Rate (Hz)', _frameRateCtrl),
                      ]),

                      const SizedBox(height:24),

                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton.icon(
                          onPressed: _isAnalyzing ? null : _handleAnalysis,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF8B6F5C),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                          icon: _isAnalyzing
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                                  ),
                                )
                              : const Icon(Icons.analytics),
                            label: Text(
                              _isAnalyzing
                                ?(_isProcessing
                                  ? 'Extraction keypoints...'
                                  :'Analyse en cours...')
                                : 'Lancer l\'analyse'
                              ),
                        ),
                      ),

                      const SizedBox(height:24),

                      //Résultats MediaPipe

                      if (_selectedModel == 'MediaPipe' && _holisticResults != null) ...[
                        _buildMediaPipeResultsSection(),
                        const SizedBox(height: 16),
                      ],

                      //Résultats serveur
                      if (_currentMotionData != null) _buildAnalysisResultsSection(),

                      if (_serverMotionData != null && _serverMotionType != null)
                        _buildServerResultsSection(),
                        
                      

                      const SizedBox(height: 24),
                      
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton.icon(
                          onPressed: () => Navigator.pushNamedAndRemoveUntil(
                            context,
                            '/',
                            (route) => false,
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF8B6F5C),
                            foregroundColor: Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                          ),
                          icon: const Icon(Icons.home_rounded),
                          label: const Text('Retour au menu'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),

          // Chargement lors de l'analyse
          if (_isAnalyzing)
            Container(
              color: Colors.black54,
              child: Center(
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const CircularProgressIndicator(),
                        const SizedBox(height: 16),
                        Text(
                          _analysisProgress,
                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Cela peut prendre plusieurs minutes',
                          style: TextStyle(fontSize: 14, color: Colors.grey),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  //***  Fonction principale d'analyse (qui route vers analyse mediapipe ou analyse serveur) ***//
  Future<void> _handleAnalysis() async {
    if (!_validateInputs()) return;

    if(_selectedModel == 'MediaPipe'){
      await _handleMediaPipeAnalysis();
    } else {
      await _handleServerAnalysis();
    }
  }


  //***Analyse MediaPipe***//

  Future<void> _handleMediaPipeAnalysis() async{

    final startTime = double.parse(_startTimeCtrl.text);
    final endTime = double.parse(_endTimeCtrl.text);
    final frameRate = int.parse(_frameRateCtrl.text);

    setState(() {
      _isAnalyzing = true;
      _isProcessing = true;
      _analysisProgress = 'Extraction des keypoints MediaPipe...';
      _currentMotionData = null;
      _currentMotionType = null;
    });

    try {

      //Calcul des keypoints/landmarks avec MediaPipe
      print('Calcul des keypoints MediaPipe (${frameRate} fps) ...');
            final results = await MediaPipeService.processVideo(
        _localVideoFile!.path,  // chemin local récupéré après download
        frameRate: frameRate,
      );

      //Sauvegarde des résultats en format JSON
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      final filename = 'holistic_$timestamp.json';
      await MediaPipeService.saveResultsToJson(results, filename);

      setState((){
        _holisticResults = results;
        _isProcessing = false;
        _analysisProgress = 'Analyse des mouvements...';
      });

      _showSuccess(
        'Analyse terminée\n'
        '${results.totalFrames} frames analysées\n'
        'Résultats sauvegardés format JSON'
      );

      String action = _selectedAction == 'Abduction/Adduction'
        ? 'abdadd'
        : _selectedAction == 'Flexion/Extension'
        ? 'flxext'
        : 'rotation';

      String bodyPart = _selectedLimb;
      final MotionType? motionType = _getMotionType(_selectedLimb, action, _isLateral);

      final result = await _mocapController.handle_analysis(
        results:_holisticResults,
        startTime: startTime,
        endTime: endTime,
        bodyPart: bodyPart,
        action: action,
        isLateral: _isLateral,
      );

      if (result != null){
        setState(() {
          _currentMotionData = result;
          _currentMotionType = motionType;
        });

        _showSuccess('Analyse terminée!');
      } else {
        _showError('Aucune donnée détectée pour cette analyse');
      }

    } catch(e){
      _showError('Erreur lors de l\'analyse: $e');
    } finally {
      setState(() {
        _isAnalyzing = false;
        _isProcessing = false;
        _analysisProgress = '';
      }); 
    }
  }


  //*** Analyse sur serveur (AlphaPose/MMPose/6DRepNet) ***//

  Future<void> _handleServerAnalysis() async {

        setState(() {
      _isAnalyzing = true;
      _analysisProgress = 'Analyse en cours...';
      _serverMotionData = null;
      _serverMotionType = null;
      _lastResultFileName = null;
      _skeletonChewieController?.dispose();
      _skeletonVideoController?.dispose();
      _skeletonChewieController = null;
      _skeletonVideoController = null;
    });

        try {
      final requestData = {
        'video_id': widget.videoId,
        'model': _selectedModel,
        'limb': _selectedLimb,
        'action': _selectedAction,
        'start_time': double.parse(_startTimeCtrl.text),
        'end_time': double.parse(_endTimeCtrl.text),
        'frame_rate': int.parse(_frameRateCtrl.text),
        'threshold_min': _thresholdMinCtrl.text.isNotEmpty
            ? double.parse(_thresholdMinCtrl.text) : null,
        'threshold_max': _thresholdMaxCtrl.text.isNotEmpty
            ? double.parse(_thresholdMaxCtrl.text) : null,
        'zoom_start': _zoomStartCtrl.text.isNotEmpty
            ? double.parse(_zoomStartCtrl.text) : null,
        'zoom_end': _zoomEndCtrl.text.isNotEmpty
            ? double.parse(_zoomEndCtrl.text) : null,
        'limit_min': _limitMinCtrl.text.isNotEmpty
            ? double.parse(_limitMinCtrl.text) : null,
        'limit_max': _limitMaxCtrl.text.isNotEmpty
            ? double.parse(_limitMaxCtrl.text) : null,
        'delete_last_slices': _deleteLastSlices,
        'include_limit_of_data': _includeLimitOfData,
        'crop_coords': _calculateCropCoords(),
        'username': 'flutter_user',
      };
 
      final response = await http
          .post(
            Uri.parse('${server.baseUrl}/api/analyze'),  // ← server.baseUrl, pas API_URL
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(requestData),
          )
          .timeout(
            const Duration(minutes: 20),
            onTimeout: () => throw Exception('L\'analyse a pris trop de temps'),
          );
 
      if (response.statusCode == 200) {
        final result = jsonDecode(response.body);
        final data = result['data'] as Map<String, dynamic>? ?? {};
 
        final rawTimes = (data['time_series'] as List? ?? [])
            .map((v) => (v as num).toDouble()).toList();
        final rawAngles = data['angles'] as List? ?? [];
 
        final values = rawAngles.isNotEmpty
            ? (rawAngles[0] as List).map((v) => (v as num).toDouble()).toList()
            : <double>[];
        final valuesLeft = rawAngles.length > 1
            ? (rawAngles[1] as List).map((v) => (v as num).toDouble()).toList()
            : null;
 
        final action = _selectedAction == 'Abduction/Adduction'
            ? 'abdadd'
            : _selectedAction == 'Flexion/Extension' ? 'flxext' : 'rotation';
 
        setState(() {
          _serverMotionData = MotionData(
            times: rawTimes,
            values: values,
            valuesLeft: valuesLeft,
            missingKeypoints: [],
          );
          _serverMotionType = _getMotionType(_selectedLimb, action, false);
          _lastResultFileName = data['result_file_name'] as String?;
        });
 
        _showSuccess(
          'Analyse terminée!\n'
        );
      } else {
        final error = jsonDecode(response.body);
        _showError('Erreur: ${error['detail']}');
      }
    } catch (e) {
      _showError('Erreur lors de l\'analyse: $e');
    } finally {
      setState(() {
        _isAnalyzing = false;
        _analysisProgress = '';
      });
    }
  }


    // ── Vidéo squelette ──
 
  Future<void> _loadSkeletonVideo() async {
    if (_lastResultFileName == null) return;
    setState(() => _isLoadingSkeletonVideo = true);
 
    try {
      final response = await http
          .post(
            Uri.parse('${server.baseUrl}/api/skeleton-video'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'video_id': widget.videoId,
              'result_file_name': _lastResultFileName,
              'start_time': double.parse(_startTimeCtrl.text),
              'end_time': double.parse(_endTimeCtrl.text),
            }),
          )
          .timeout(const Duration(minutes: 5));
 
      if (response.statusCode == 200) {
        final dir  = await getTemporaryDirectory();
        final file = File('${dir.path}/skeleton_video.mp4');
        await file.writeAsBytes(response.bodyBytes);
 
        final skeletonController = VideoPlayerController.file(file);
        await skeletonController.initialize();
 
        setState(() {
          _skeletonVideoController?.dispose();
          _skeletonChewieController?.dispose();
          _skeletonVideoController = skeletonController;
          _skeletonChewieController = ChewieController(
            videoPlayerController: skeletonController,
            autoPlay: false,
            looping: true,
            showControls: true,
            materialProgressColors: ChewieProgressColors(
              playedColor: const Color(0xFF8B6F5C),
              handleColor: const Color(0xFF8B6F5C),
            ),
          );
        });
      } else {
        _showError('Impossible de charger la vidéo squelette');
      }
    } catch (e) {
      _showError('Erreur vidéo squelette: $e');
    } finally {
      setState(() => _isLoadingSkeletonVideo = false);
    }
  }

  

  //*** Fonctions utilitaires ***//  

    List<int> _calculateCropCoords() {
    if (widget.cropRect == null) {
      final width  = _videoController.value.size.width.toInt();
      final height = _videoController.value.size.height.toInt();
      return [0, 0, height, width];
    }
    final videoSize = _videoController.value.size;
    final cropRect  = widget.cropRect!;
    final x      = (cropRect.left   * videoSize.width).round();
    final y      = (cropRect.top    * videoSize.height).round();
    final width  = (cropRect.width  * videoSize.width).round();
    final height = (cropRect.height * videoSize.height).round();
    return [y, x, height, width];
  }


  bool _validateInputs() {
    try {
      final startTime = double.parse(_startTimeCtrl.text);
      final endTime = double.parse(_endTimeCtrl.text);
      final frameRate = int.parse(_frameRateCtrl.text);

      if (startTime >= endTime) {
        _showError('Le temps de fin doit être supérieur au temps de début');
        return false;
      }

      if (endTime - startTime < 2) {
        _showError('L\'analyse doit porter sur au moins 2 secondes');
        return false;
      }

      if (frameRate <= 0 || frameRate > 60){
        _showError('Le frame rate doit être entre 1 et 60 Hz');
        return false;
      }

      if(_selectedModel == 'MediaPipe'){
        final videoDuration = _videoController.value.duration.inMilliseconds / 1000.0;

        if(!_mocapController.verify_start_and_end_inputs(
          startTime: startTime, 
          endTime: endTime,
          videoDuration: videoDuration,
        )) {
          _showError('Temps de début/fin invalides');
          return false;
        }

        if(!_mocapController.verify_threshold_inputs(
          thresholdMinText: _thresholdMinCtrl.text,
          thresholdMaxText: _thresholdMaxCtrl.text,
        )) {
          _showError('Valeurs de seuil invalides');
          return false; 
        }

        if(!_mocapController.verify_zoom_inputs(
          zoomStartText: _zoomStartCtrl.text,
          zoomEndText: _zoomEndCtrl.text,
          startTime: startTime,
          endTime: endTime,
        )) {
          _showError('Valeurs de zoom invalides');
          return false;
        }

        if(!_mocapController.verify_limit_inputs(
          limiMinText: _limitMinCtrl.text,
          limitMaxText: _limitMaxCtrl.text,
        )) {
          _showError('Valeurs de limite invalides');
          return false;
        }
      }

      return true;
    } catch (e) {
      _showError('Veuillez entrer des valeurs numériques valides');
      return false;
    }
  }

  bool _shouldShowLateralOption() {
    if(_selectedModel != 'MediaPipe') return false;
    
    if(_selectedAction == 'Flexion/Extension'){
      return _selectedLimb == 'Head' || _selectedLimb == 'Arm';
    }
    return false;
  }

  void _showError(String message){
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content:Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds:5),
      ),
    );
  }

  void _showSuccess(String message){
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content:Text(message),
        backgroundColor: const Color(0xFF8B6F5C),
        duration: const Duration(seconds:5),
      ),
    );
  }

  MotionType? _getMotionType(String bodyPart, String action, bool isLateral) {
  if (bodyPart == 'Head') {
    if (action == 'abdadd') return MotionType.HEAD_ABDADD;
    if (action == 'flxext') return isLateral ? MotionType.HEAD_ROT_LAT : MotionType.HEAD_FLXEXT;
    if (action == 'rotation') return MotionType.HEAD_ROTATION;
  } else if (bodyPart == 'Shoulder') {
    if (action == 'abdadd') return MotionType.SHOULDER_ABDADD;
    if (action == 'flxext') return MotionType.SHOULDER_FLXEXT;
  } else if (bodyPart == 'Torso') {
    if (action == 'abdadd') return MotionType.TORSO_ABDADD;
    if (action == 'flxext') return MotionType.TORSO_FLXEXT;
    if (action == 'rotation') return MotionType.TORSO_ROTATION;
  } else if (bodyPart == 'Arm') {
    if (action == 'abdadd') return MotionType.ARM_ABDADD;
    if (action == 'flxext') return isLateral ? MotionType.ARM_FLXEXT_LAT : MotionType.ARM_FLXEXT;
  } else if (bodyPart == 'Fore Arm') {
    if (action == 'flxext') return MotionType.FOREARM_FLXEXT;
  }
  return null;
}

  
  // *** Widgets d'affichage des résultats ***//

  Widget _buildMediaPipeResultsSection(){
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.blue[50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.blue),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.info_outline, color: Colors.blue),
              SizedBox(width: 8),
              Text(
                'Analyse MediaPipe terminée',
                style:
                    TextStyle(fontWeight: FontWeight.bold, color: Colors.blue),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildResultRow('Frames analysées','${_holisticResults!.totalFrames}'),
          _buildResultRow('Durée', '${_holisticResults!.duration} ms'),
          _buildResultRow(
              'Frame rate', '${_holisticResults!.frameRate} fps'),
        ],
      ),
    );
  }

  Widget _buildAnalysisResultsSection(){
    return Container(
      margin: const EdgeInsets.only(top:16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.green [50],
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.check_circle, color:Colors.green),
              SizedBox(width:8),
              Text(
                'Analyse terminée',
                style:TextStyle(
                  fontWeight: FontWeight.bold,color: Colors.green),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildResultRow('Nom',_mocapController.analysisName),
          _buildResultRow('Points analysés', '${_currentMotionData!.times.length}'),
          _buildResultRow('Durée', '${_currentMotionData!.times.last.toStringAsFixed(2)}s'),

          if(_currentMotionData!.missingKeypoints.isNotEmpty)
            Padding(
              padding:const EdgeInsets.only(top:8),
              child:Text(
                'Keypoints manquants: ${_currentMotionData!.missingKeypoints.join(", ")}',
                style: const TextStyle(color: Colors.orange, fontSize: 12),
              ),
            ),

            const SizedBox(height: 16),
            const Text('Valeurs (times, values):', style: TextStyle(fontWeight:FontWeight.bold)),
            const SizedBox(height: 8),

            //Affichage des premières valeurs
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.grey[200],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Times: ${_currentMotionData!.times.take(5).map((t) => t.toStringAsFixed(2)).join(", ")}...\n'
                'Values: ${_currentMotionData!.values.take(5).map((v) => v.toStringAsFixed(2)).join(", ")}...',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
            ),

            const SizedBox(height: 24),

            //Graphiques
            MotionPlotting.buildMotionPlots(
              plot_name: _mocapController.analysisName,
              motion_data: _currentMotionData!,
              plot_color: const Color(0xFF8B6F5C),
              motion_type: _currentMotionType!, // ← à déterminer
              is_limit_option_selected: _includeLimitOfData,
              threshold_min: double.tryParse(_thresholdMinCtrl.text) ?? -1000,
              threshold_max: double.tryParse(_thresholdMaxCtrl.text) ?? -1000,
              zoom_start: double.tryParse(_zoomStartCtrl.text) ?? -1,
              zoom_end: double.tryParse(_zoomEndCtrl.text) ?? -1,
            ),
        ],
      ),
    );
  }

    Widget _buildServerResultsSection() {
    return _buildSection('Résultats', Icons.show_chart_rounded, [
      MotionPlotting.buildMotionPlots(
        plot_name: '$_selectedLimb – $_selectedAction',
        motion_data: _serverMotionData!,
        plot_color: const Color(0xFF8B6F5C),
        motion_type: _serverMotionType!,
        is_limit_option_selected: _includeLimitOfData,
        threshold_min: double.tryParse(_thresholdMinCtrl.text) ?? -1000,
        threshold_max: double.tryParse(_thresholdMaxCtrl.text) ?? -1000,
        zoom_start: double.tryParse(_zoomStartCtrl.text) ?? -1,
        zoom_end: double.tryParse(_zoomEndCtrl.text) ?? -1,
      ),
      if (_lastResultFileName != null) ...[
        const SizedBox(height: 16),
        SizedBox(
          width: double.infinity,
          height: 46,
          child: ElevatedButton.icon(
            onPressed: _isLoadingSkeletonVideo ? null : _loadSkeletonVideo,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFF5F0EB),
              foregroundColor: const Color(0xFF5C4033),
              elevation: 0,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            icon: _isLoadingSkeletonVideo
                ? const SizedBox(
                    width: 18, height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF8B6F5C)),
                  )
                : const Icon(Icons.accessibility_rounded),
            label: Text(_isLoadingSkeletonVideo ? 'Chargement...' : 'Voir vidéo avec squelette'),
          ),
        ),
      ],
      if (_skeletonChewieController != null) ...[
        const SizedBox(height: 12),
        const Text('Vidéo avec squelette',
            style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Color(0xFF5C4033))),
        const SizedBox(height: 8),
        AspectRatio(
          aspectRatio: 16 / 9,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Chewie(controller: _skeletonChewieController!),
          ),
        ),
      ],
    ]);
  }

  Widget _buildSection(String title, IconData icon, List<Widget> children) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F0EB),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, size: 18, color: const Color(0xFF8B6F5C)),
              ),
              const SizedBox(width: 10),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF5C4033),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ...children,
        ],
      ),
    );
  }

  Widget _buildRadio(String value) {
    return RadioListTile<String>(
      value: value,
      groupValue: _selectedModel,
      onChanged: (v) => setState(() => _selectedModel = v!),
      title: Text(value, style: const TextStyle(fontSize: 14)),
      contentPadding: EdgeInsets.zero,
      dense: true,
    );
  }

  Widget _buildSwitch(String label, bool value, ValueChanged<bool> onChanged) {
    return SwitchListTile(
      value: value,
      onChanged: onChanged,
      title: Text(label, style: const TextStyle(fontSize: 14)),
      contentPadding: EdgeInsets.zero,
      dense: true,
    );
  }

  Widget _buildChip(String label) {
    final isSelected = _selectedLimb == label;
    return FilterChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => setState(() => _selectedLimb = label),
      selectedColor: const Color(0xFF8B6F5C),
      backgroundColor: const Color(0xFFF5F0EB),
      labelStyle: TextStyle(
        color: isSelected ? Colors.white : const Color(0xFF5C4033),
        fontSize: 13,
      ),
    );
  }

  Widget _buildActionBtn(String action) {
    final isSelected = _selectedAction == action;
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: () => setState(() => _selectedAction = action),
        style: ElevatedButton.styleFrom(
          backgroundColor: isSelected ? const Color(0xFF8B6F5C) : const Color(0xFFF5F0EB),
          foregroundColor: isSelected ? Colors.white : const Color(0xFF5C4033),
          elevation: 0,
          padding: const EdgeInsets.symmetric(vertical: 12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
        child: Text(action, style: const TextStyle(fontSize: 14)),
      ),
    );
  }

  Widget _buildField(String label, TextEditingController controller) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF5C4033))),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: InputDecoration(
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Color(0xFFE0D5CC)),
            ),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            filled: true,
            fillColor: Colors.white,
          ),
          style: const TextStyle(fontSize: 14),
        ),
      ],
    );
  }

  Widget _buildResultRow(String label, String value){
    return Padding(
      padding:const EdgeInsets.symmetric(vertical:4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(fontSize:13)),
          Text(
            value,
            style: const TextStyle(fontWeight: FontWeight.bold,fontSize: 13),
          ),
        ],
      ),
    );
  }

   //Méthodes de navigation dans la vidéo

   Future<void> _previousFrame() async {
      await _videoController.pause();
      final pos = _videoController.value.position - const Duration(seconds: 1);
      await _videoController.seekTo(pos < Duration.zero ? Duration.zero : pos);
      setState(() {});
    }

    Future<void> _nextFrame() async {
      await _videoController.pause();
      await _videoController.pause();
      final pos = _videoController.value.position + const Duration(seconds: 1);
      final max = _videoController.value.duration;
      await _videoController.seekTo(pos > max ? max : pos);
      setState(() {});
    }

}
