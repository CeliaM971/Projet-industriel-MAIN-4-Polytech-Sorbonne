import '../app_config.dart';

class ServerConfig {
  ServerConfig._();
  static final instance = ServerConfig._();

  String baseUrl = AppConfig.baseUrl;

  String? _accessToken;
  int? _userId;

  void setToken(String token) => _accessToken = token;
  void setUserId(int id) => _userId = id;

  String? get token => _accessToken;
  int? get userId => _userId;


  bool get isAuthenticated => _accessToken != null && _userId != null;

  Map<String, String> authHeaders() {
    if (_accessToken == null) {
      throw Exception("Non authentifié");
    }
    return {
      "Content-Type": "application/json",
      "Authorization": "Bearer $_accessToken",
    };
  }
}
