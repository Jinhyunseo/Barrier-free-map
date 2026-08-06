import 'package:flutter/material.dart';
import 'package:kakao_map_plugin/kakao_map_plugin.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  AuthRepository.initialize(appKey: '670b90c371e83c8aa86726e82acc3cf3');
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: RouteSearchScreen(),
    );
  }
}

class RouteSearchScreen extends StatefulWidget {
  const RouteSearchScreen({super.key});

  @override
  State<RouteSearchScreen> createState() => _RouteSearchScreenState();
}

class _RouteSearchScreenState extends State<RouteSearchScreen> {
  KakaoMapController? mapController;

  // 입력 컨트롤러
  final TextEditingController _startController = TextEditingController(text: '야탑역');
  final TextEditingController _endController = TextEditingController(text: '판교역');

  // 사용자 유형 선택 State
  String selectedUserType = '휠체어';
  final List<String> userTypes = ['휠체어', '노약자', '유모차'];

  // 지도 좌표 데이터
  final LatLng startLatLng = LatLng(37.411337, 127.128696);
  final LatLng endLatLng = LatLng(37.394776, 127.11116);

  List<Marker> markers = [];
  List<Polyline> polylines = [];

  @override
  void initState() {
    super.initState();
    _initMapElements();
  }

  void _initMapElements() {
    markers = [
      Marker(markerId: 'start', latLng: startLatLng),
      Marker(markerId: 'end', latLng: endLatLng),
    ];

    List<LatLng> detailedPath = [
      LatLng(37.411337, 127.128696),
      LatLng(37.410100, 127.128200),
      LatLng(37.405500, 127.126800),
      LatLng(37.401200, 127.125100),
      LatLng(37.399800, 127.120500),
      LatLng(37.398500, 127.116200),
      LatLng(37.397100, 127.113800),
      LatLng(37.395800, 127.112200),
      LatLng(37.394776, 127.111160),
    ];

    polylines = [
      Polyline(
        polylineId: 'route_line',
        points: detailedPath,
        strokeColor: Colors.blue,
        strokeWidth: 6,
        strokeOpacity: 0.8,
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // 1. 배경: 카카오맵 지도 표시
          KakaoMap(
            onMapCreated: (controller) async {
              mapController = controller;
              setState(() {});
              if (markers.isNotEmpty) await mapController?.addMarker(markers: markers);
              if (polylines.isNotEmpty) await mapController?.addPolyline(polylines: polylines);
            },
            center: startLatLng,
            markers: markers,
            polylines: polylines,
          ),

          // 2. 상단 패널: 출발지/목적지 입력 & 사용자 유형 선택
          Positioned(
            top: 50,
            left: 16,
            right: 16,
            child: Card(
              elevation: 6,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // 출발지 입력
                    TextField(
                      controller: _startController,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.my_location, color: Colors.blue),
                        hintText: '출발지 입력',
                        isDense: true,
                        border: InputBorder.none,
                      ),
                    ),
                    const Divider(height: 1),
                    // 목적지 입력
                    TextField(
                      controller: _endController,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.location_on, color: Colors.red),
                        hintText: '목적지 입력',
                        isDense: true,
                        border: InputBorder.none,
                      ),
                    ),
                    const SizedBox(height: 10),
                    
                    // 사용자 유형 선택 칩 (Horizontal Scroll)
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: userTypes.map((type) {
                          final isSelected = selectedUserType == type;
                          return Padding(
                            padding: const EdgeInsets.only(right: 6.0),
                            child: ChoiceChip(
                              label: Text(type),
                              selected: isSelected,
                              selectedColor: Colors.blue.shade100,
                              onSelected: (selected) {
                                if (selected) {
                                  setState(() {
                                    selectedUserType = type;
                                  });
                                }
                              },
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // 3. 하단 바텀시트: 추천 경로 요약 & 추천 이유 확인
          DraggableScrollableSheet(
            initialChildSize: 0.28, // 처음 가로채는 화면 비율 (28%)
            minChildSize: 0.15,     // 최소 내렸을 때 비율
            maxChildSize: 0.60,     // 위로 최대 올렸을 때 비율
            builder: (BuildContext context, ScrollController scrollController) {
              return Container(
                decoration: const BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                  boxShadow: [BoxShadow(blurRadius: 10, color: Colors.black26)],
                ),
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(20),
                  children: [
                    // 드래그 핸들 바
                    Center(
                      child: Container(
                        width: 40,
                        height: 5,
                        decoration: BoxDecoration(
                          color: Colors.grey[300],
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                    const SizedBox(height: 15),

                    // 경로 기본 정보
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '$selectedUserType 맞춤 추천 경로',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const Text(
                          '약 22분 (1.8km)',
                          style: TextStyle(fontSize: 16, color: Colors.blue, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 15),

                    // 4. 추천 이유 표시 영역
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start, // O 정답
                        children: [
                          const Text(
                            '💡 이 경로를 추천하는 이유',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          const SizedBox(height: 8),
                          _buildReasonItem('경사도 5% 이하의 평지 위주 도로'),
                          _buildReasonItem('턱 없는 인도 및 엘리베이터 이동 동선 포함'),
                          _buildReasonItem('보도블록 파손 구간 및 횡단보도 우회 적용'),
                        ],
                      ),
                    ),
                    const SizedBox(height: 15),

                    // 안내 시작 버튼
                    ElevatedButton(
                      onPressed: () {
                        // 경로 안내 시작 액션
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blueAccent,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('경로 안내 시작', style: TextStyle(fontSize: 16, color: Colors.white)),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  // 추천 이유 아이콘 텍스트 위젯
  Widget _buildReasonItem(String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.0),
      child: Row(
        children: [
          const Icon(Icons.check_circle_outline, size: 16, color: Colors.green),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, color: Colors.black87))),
        ],
      ),
    );
  }
}
