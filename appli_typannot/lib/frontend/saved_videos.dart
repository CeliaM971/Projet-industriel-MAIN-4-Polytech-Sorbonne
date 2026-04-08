import 'dart:convert';
import 'dart:io';

import 'server.dart';

import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:http/http.dart' as http;

class SavedVideoEntry {
  final String serverUrl;
  final String name;
  final String videoId;
  final DateTime uploadDate;
  final int? groupId;

  SavedVideoEntry({
    required this.serverUrl,
    required this.name,
    required this.videoId,
    required this.uploadDate,
    this.groupId,
  });

  Map<String, dynamic> toJson() => {
        'serverUrl': serverUrl,
        'name': name,
        'videoId': videoId,
        'uploadDate': uploadDate.toIso8601String(),
        'groupId': groupId,
      };

  static SavedVideoEntry fromJson(Map<String, dynamic> json) {
    return SavedVideoEntry(
      serverUrl: json['serverUrl'] as String,
      name: json['name'] as String,
      videoId: json['videoId'] as String,
      uploadDate: DateTime.parse(json['uploadDate'] as String),
      groupId: json['groupId'] as int?,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is SavedVideoEntry && videoId == other.videoId;

  @override
  int get hashCode => videoId.hashCode;
}

class SavedVideosService {
  SavedVideosService._();
  static final instance = SavedVideosService._();

  Future<File> _indexFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File(p.join(dir.path, 'saved_videos_index.json'));
  }

  Future<List<SavedVideoEntry>> loadEntries() async {
    try {
      final index = await _indexFile();
      if (!await index.exists()) return [];
      final raw = await index.readAsString();
      final decoded = jsonDecode(raw);
      if (decoded is List) {
        return decoded
            .map((e) => SavedVideoEntry.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (e) {
      print("Erreur chargement index: $e");
    }
    return [];
  }

  Future<void> saveEntries(List<SavedVideoEntry> entries) async {
    final index = await _indexFile();
    await index.writeAsString(
      jsonEncode(entries.map((e) => e.toJson()).toList()),
    );
  }

  Future<List<SavedVideoEntry>> fetchServerVideos() async {
    final server = ServerConfig.instance;
    final token = server.token;
    if (token == null) return [];

    try {
      final response = await http.get(
        Uri.parse('${server.baseUrl}/videos/my-videos'),
        headers: {'Authorization': 'Bearer $token'},
      );

      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        return data.map((json) {
          return SavedVideoEntry(
            videoId: json['id'].toString(),
            name: json['title'] ?? 'Vidéo inconnue',
            serverUrl: '${server.baseUrl}/videos/${json['id']}/download',
            uploadDate: DateTime.parse(json['created_at']),
            groupId: json['group_id'],
          );
        }).toList();
      } else {
        print("Erreur récupération serveur: ${response.statusCode}");
      }
    } catch (e) {
      print("Erreur fetchServerVideos: $e");
    }
    return [];
  }

  Future<List<SavedVideoEntry>> fetchGroupVideos(int groupId) async {
    final server = ServerConfig.instance;
    final token = server.token;
    if (token == null) {
      print("❌ Pas de token d'authentification");
      return [];
    }

    try {
      print("🔍 Récupération des vidéos du groupe $groupId");

      final response = await http.get(
        Uri.parse('${server.baseUrl}/videos/groups/$groupId/videos'),
        headers: server.authHeaders(),
      );

      print("📦 fetchGroupVideos Status: ${response.statusCode}");
      print("📦 fetchGroupVideos Body: ${response.body}");

      if (response.statusCode == 200) {
        final List data = jsonDecode(response.body);
        final videos = data.map((json) {
          return SavedVideoEntry(
            videoId: json['id'].toString(),
            name: json['title'] ?? 'Vidéo inconnue',
            serverUrl: '${server.baseUrl}/videos/${json['id']}/download',
            uploadDate: DateTime.parse(json['created_at']),
            groupId: json['group_id'],
          );
        }).toList();

        print("✅ ${videos.length} vidéos récupérées pour le groupe $groupId");
        return videos;
      } else {
        print("❌ Erreur: ${response.statusCode} - ${response.body}");
      }
    } catch (e) {
      print("❌ Exception lors de la récupération des vidéos du groupe: $e");
    }
    return [];
  }

  Future<SavedVideoEntry?> saveVideo(File source, {int? groupId}) async {
    try {
      final uploadResult = await sendToBackend(source.path, groupId: groupId);
      if (uploadResult == null) return null;

      final entry = SavedVideoEntry(
        serverUrl: uploadResult['url'],
        name: uploadResult['name'] ?? p.basenameWithoutExtension(source.path),
        videoId: uploadResult['id'],
        uploadDate: DateTime.now(),
        groupId: uploadResult['group_id'],
      );

      final entries = await loadEntries();
      entries.insert(0, entry);
      await saveEntries(entries);

      return entry;
    } catch (e) {
      print("Erreur saveVideo: $e");
      return null;
    }
  }

  Future<void> renameVideo(String videoId, String newName) async {
  // SUPPRIMER la dépendance au cache local, appeler directement le serveur
    try {
      final response = await http.patch(
        Uri.parse("${ServerConfig.instance.baseUrl}/videos/$videoId"),
        headers: ServerConfig.instance.authHeaders(),
        body: jsonEncode({"title": newName}),
      );

      if (response.statusCode != 200) {
        print("Erreur rename sur serveur: ${response.statusCode} - ${response.body}");
      } else {
        print("Renommage réussi sur le serveur");
      }
    } catch (e) {
      print("Erreur rename sur serveur: $e");
    } 
  }

  Future<void> deleteVideo(String videoId) async {
    try {
      await http.delete(
        Uri.parse("${ServerConfig.instance.baseUrl}/videos/$videoId"),
        headers: ServerConfig.instance.authHeaders(),
      );
    } catch (e) {
      print("Erreur suppression serveur: $e");
    }
}

  Future<File?> downloadVideo(String videoId, String serverUrl) async {
    try {
      final response = await http.get(
        Uri.parse("${ServerConfig.instance.baseUrl}/videos/$videoId/download"),
        headers: ServerConfig.instance.authHeaders(),
      );

      if (response.statusCode == 200) {
        final tempDir = await getTemporaryDirectory();
        final file = File(p.join(tempDir.path, 'video_$videoId.mp4'));
        await file.writeAsBytes(response.bodyBytes);
        return file;
      }
    } catch (e) {
      print("Erreur téléchargement: $e");
    }
    return null;
  }
}

Future<Map<String, dynamic>?> sendToBackend(String localPath, {int? groupId}) async {
  try {
    final server = ServerConfig.instance;
    final userId = server.userId;
    final token = server.token;

    if (userId == null || token == null) {
      print("Erreur: utilisateur non identifié ou non authentifié");
      return null;
    }



    final endpoint = groupId != null
        ? "${server.baseUrl}/videos/users/$groupId/videos/upload"
        : "${server.baseUrl}/videos/users/$userId/videos/upload";

    final req = http.MultipartRequest("POST", Uri.parse(endpoint));
    req.headers['Authorization'] = 'Bearer $token';
    req.fields['title'] = p.basenameWithoutExtension(localPath);
    req.fields['description'] = 'Vidéo uploadée depuis l\'app';
    req.files.add(await http.MultipartFile.fromPath("file", localPath));

    final res = await req.send();
    final body = await res.stream.bytesToString();

    print("URL: ${req.url}");
    print("Headers: ${req.headers}");
    print("Fields: ${req.fields}");
    print("status = ${res.statusCode}");
    print("body = $body");

    if (res.statusCode == 200 || res.statusCode == 201) {
      final json = jsonDecode(body);
      return {
        'id': json['id'].toString(),
        'url': "${server.baseUrl}/videos/${json['id']}/download",
        'name': json['title'] ?? p.basenameWithoutExtension(localPath),
        'group_id': json['group_id'],
      };
    }
  } catch (e) {
    print("Erreur sendToBackend: $e");
  }
  return null;
}
