let video;//test
let bodyPose;
let poses = [];
let poseHistory = []; // Array to store pose history
const maxHistoryLength = 100; // Increased history length for smoother trails
const blurRadius = 20; // Radius for blending poses
let connections;
let recordButton;
let isRecording = false;

// Three.js variables
let camera3D, scene, renderer;
let controls; // Orbit controls
let posePoints = [];
let poseLines = [];
let faceCircle; // Added for face circle

function preload() {
  // Load Three.js and OrbitControls scripts
  let threeScript = document.createElement('script');
  threeScript.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
  document.head.appendChild(threeScript);

  let orbitScript = document.createElement('script'); 
  orbitScript.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js';
  document.head.appendChild(orbitScript);

  bodyPose = ml5.bodyPose();
}

function setup() {
  // Wait for Three.js to load
  if (typeof THREE === 'undefined') {
    setTimeout(setup, 100);
    return;
  }

  // Set up Three.js scene
  scene = new THREE.Scene();
  camera3D = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
  renderer = new THREE.WebGLRenderer({ antialias: true }); // Enable antialiasing for smoother lines
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  // Wait for OrbitControls to load
  if (typeof THREE.OrbitControls === 'undefined') {
    setTimeout(setup, 100); 
    return;
  }

  // Set up OrbitControls
  controls = new THREE.OrbitControls(camera3D, renderer.domElement);
  controls.enableDamping = true; // Add smooth damping
  controls.dampingFactor = 0.05;
  controls.screenSpacePanning = false;
  controls.minDistance = 100;
  controls.maxDistance = 800;

  // Set up video capture
  video = createCapture(VIDEO);
  video.size(640, 480);
  video.hide();

  bodyPose.detectStart(video, gotPoses);
  connections = bodyPose.getSkeleton();

  // Create record/stop button
  recordButton = createButton('⏺RECORD');
  recordButton.position(10, window.innerHeight - 50);
  recordButton.mousePressed(toggleRecording);
  recordButton.style('font-size', '24px');
  recordButton.style('padding', '5px 15px');

  // Position camera
  camera3D.position.z = 500;

  // Add lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(0, 1, 1);
  scene.add(directionalLight);

  animate();
}

function toggleRecording() {
  isRecording = !isRecording;
  if (isRecording) {
    recordButton.html('⏹STOP');
    poseHistory = [];
  } else {
    recordButton.html('⏺RECORD');
  }
}

function animate() {
  requestAnimationFrame(animate);
  if (controls) controls.update(); // Update orbit controls if available
  updatePoses();
  renderer.render(scene, camera3D);
}

function cleanupScene() {
  while(scene.children.length > 0) {
    const object = scene.children[0];
    if(object.geometry) object.geometry.dispose();
    if(object.material) {
      if(Array.isArray(object.material)) {
        object.material.forEach(material => material.dispose());
      } else {
        object.material.dispose();
      }
    }
    scene.remove(object);
  }
  
  posePoints = [];
  poseLines = [];
  
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene.add(ambientLight);
  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.5);
  directionalLight.position.set(0, 1, 1);
  scene.add(directionalLight);
}

function updatePoses() {
  // Cleanup previous frame
  posePoints.forEach(point => {
    if(point.geometry) point.geometry.dispose();
    if(point.material) point.material.dispose();
    scene.remove(point);
  });
  poseLines.forEach(line => {
    if(line.geometry) line.geometry.dispose();
    if(line.material) line.material.dispose();
    scene.remove(line);
  });
  if(faceCircle) {
    if(faceCircle.geometry) faceCircle.geometry.dispose();
    if(faceCircle.material) faceCircle.material.dispose();
    scene.remove(faceCircle);
  }
  posePoints = [];
  poseLines = [];

  // Draw historical poses with smooth transitions
  if (isRecording && poseHistory.length > 0) {
    poseHistory.forEach((historicalPose, index) => {
      const opacity = Math.pow((index + 1) / poseHistory.length, 2); // Quadratic fade for smoother transition
      
      if (historicalPose[0] && historicalPose[0].keypoints) {
        // Create smoothed lines between keypoints
        connections.forEach(connection => {
          const pointA = historicalPose[0].keypoints[connection[0]];
          const pointB = historicalPose[0].keypoints[connection[1]];
          
          if (pointA && pointB && pointA.confidence > 0.1 && pointB.confidence > 0.1) {
            // Create curved line between points
            const curve = new THREE.QuadraticBezierCurve3(
              new THREE.Vector3(pointA.x - 320, -pointA.y + 240, 0),
              new THREE.Vector3((pointA.x + pointB.x)/2 - 320, (-pointA.y - pointB.y)/2 + 240, 20), // Control point
              new THREE.Vector3(pointB.x - 320, -pointB.y + 240, 0)
            );

            const points = curve.getPoints(10);
            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const material = new THREE.LineBasicMaterial({
              color: new THREE.Color(0.5, 0.8, 1), // Softer blue
              transparent: true,
              opacity: opacity * 0.4,
              linewidth: 5 // Thicker lines
            });
            
            const line = new THREE.Line(geometry, material);
            scene.add(line);
            poseLines.push(line);
          }
        });
      }
    });
  }

  // Draw current pose with thicker, smoother lines
  if (poses.length > 0 && connections && connections.length > 0) {
    const pose = poses[0];
    
    if (pose.keypoints) {
      // Get face keypoints (0 is nose, 1-4 are eyes and ears)
      const facePoints = pose.keypoints.slice(0, 5).filter(point => point.confidence > 0.1);
      
      if(facePoints.length > 0) {
        // Calculate center and radius of face circle
        let centerX = 0, centerY = 0;
        facePoints.forEach(point => {
          centerX += point.x;
          centerY += point.y;
        });
        centerX = centerX / facePoints.length;
        centerY = centerY / facePoints.length;
        
        // Calculate radius as distance to furthest face point
        let maxDist = 0;
        facePoints.forEach(point => {
          const dist = Math.sqrt(Math.pow(point.x - centerX, 2) + Math.pow(point.y - centerY, 2));
          maxDist = Math.max(maxDist, dist);
        });
        
        // Create face circle
        const circleGeometry = new THREE.CircleGeometry(maxDist * 1.2, 32);
        const circleMaterial = new THREE.MeshBasicMaterial({
          color: 0x00ff00,
          transparent: true,
          opacity: 0.2,
          side: THREE.DoubleSide
        });
        faceCircle = new THREE.Mesh(circleGeometry, circleMaterial);
        faceCircle.position.set(centerX - 320, -centerY + 240, 0);
        scene.add(faceCircle);
      }

      // Draw keypoints as larger spheres
      pose.keypoints.forEach(keypoint => {
        if (keypoint.confidence > 0.1) {
          const geometry = new THREE.SphereGeometry(8); // Larger spheres
          const material = new THREE.MeshPhongMaterial({
            color: 0x0088ff, // Changed from green to blue
            emissive: 0x002211
          });
          const sphere = new THREE.Mesh(geometry, material);
          sphere.position.set(keypoint.x - 320, -keypoint.y + 240, 0);
          scene.add(sphere);
          posePoints.push(sphere);
        }
      });

      // Draw current skeleton with curved lines
      connections.forEach(connection => {
        const pointA = pose.keypoints[connection[0]];
        const pointB = pose.keypoints[connection[1]];
        
        if (pointA.confidence > 0.1 && pointB.confidence > 0.1) {
          const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(pointA.x - 320, -pointA.y + 240, 0),
            new THREE.Vector3((pointA.x + pointB.x)/2 - 320, (-pointA.y - pointB.y)/2 + 240, 30),
            new THREE.Vector3(pointB.x - 320, -pointB.y + 240, 0)
          );

          const points = curve.getPoints(10);
          const geometry = new THREE.BufferGeometry().setFromPoints(points);
          const material = new THREE.LineBasicMaterial({
            color: 0xff3366,
            linewidth: 6
          });
          
          const line = new THREE.Line(geometry, material);
          scene.add(line);
          poseLines.push(line);
        }
      });
    }
  }
}

function gotPoses(results) {
  poses = results;
  if(results && results.length > 0 && isRecording) {
    poseHistory.push(JSON.parse(JSON.stringify(results)));
    if(poseHistory.length > maxHistoryLength) {
      poseHistory.shift();
    }
  }
}