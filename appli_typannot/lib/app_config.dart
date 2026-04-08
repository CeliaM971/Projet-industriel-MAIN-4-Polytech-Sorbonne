import 'dart:convert';
import 'package:flutter/services.dart';

class AppConfig {
  static late String serverIp;
  static late int serverPort;
  static String get baseUrl => 'http://$serverIp:$serverPort';

  static Future<void> load() async {
    final data = await rootBundle.loadString('lib/config.json');
    final json = jsonDecode(data);
    serverIp = json['server_ip'];
    serverPort = json['server_port'];
  }
}