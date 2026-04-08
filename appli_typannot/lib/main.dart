import 'package:flutter/material.dart';

import 'frontend/homepage.dart';
import 'frontend/import_video.dart';
import 'frontend/annotate_video.dart';
import 'frontend/library.dart';
import 'frontend/skeleton_analysis.dart';
import 'frontend/login.dart';
import 'frontend/register.dart';
import 'frontend/saved_videos_list_screen.dart';
import 'frontend/group_selection_page.dart';
import 'app_config.dart';

void main() async{
  WidgetsFlutterBinding.ensureInitialized();
  await AppConfig.load();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      initialRoute: '/login',
      routes: {
        '/': (_) => HomePage(),
        '/video': (_) => VideoPlayerScreen(),
        '/library': (_) => SavedVideosLibraryScreen(),
        '/login': (_) => LoginScreen(),
        '/register': (_) => RegisterScreen(),
        '/saved_videos': (_) => SavedVideosListScreen(),
        '/group_selection': (_) => const GroupSelectionPage(),
      },
      
      onGenerateRoute: (settings) {
        if (settings.name == '/analysis') {
          final args = settings.arguments as Map;
          final videoId = args['videoId'].toString();
          return MaterialPageRoute(
            builder: (_) => Analysis(videoId: videoId),
          );
        }

        if (settings.name == '/annotate') {
          final args = settings.arguments as Map;
          final videoId = args['videoId'].toString();
          return MaterialPageRoute(
            builder: (_) => AnnotateVideoLoader(videoId: videoId),
          );
        }

        return null;
      },
      
    );
  }
}