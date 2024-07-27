create_hover = () => {
  return WaveSurfer.Hover.create({
    lineColor: '#DDDD',
    lineWidth: 2,
    labelBackground: '#5555',
    labelColor: '#FFFF',
    labelSize: '11px',
  });
};

create_timeline = () => {
  return WaveSurfer.Timeline.create({
    height: 15,
    timeInterval: 0.1,
    primaryLabelInterval: 1,
    insertPosition: 'beforebegin',
    style: {
      fontSize: '11px',
      color: '#DDDD',
    },
  });
}

create_minimap = () => {
  return WaveSurfer.Minimap.create({
    height: 30,
    waveColor: '#DDDD',
    progressColor: '#9999',
    normalize: true,
    plugins: [WaveSurfer.Hover.create({
        lineColor: '#DDDD',
        lineWidth: 1,
        labelBackground: '#5555',
        labelColor: '#FFFF',
        labelSize: '11px',
    })],
  });
}

create_regions = () => {
  regions = WaveSurfer.Regions.create();
  regions.enableDragSelection({color: 'rgba(255, 255, 255, 0.2)'});
  return regions;
}

create_spectrogram = () => {
  return WaveSurfer.Spectrogram.create({
    labels: true,
    colorMap: 'roseus',
    fftSamples: 2048,
  });
}

create_zoom = () => {
  return WaveSurfer.Zoom.create({
      scale: 0.5,
      maxZoom: 1000,
  });
}

formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const secondsRemainder = Math.round(seconds) % 60;
  const paddedSeconds = `0${secondsRemainder}`.slice(-2);
  return `${minutes}:${paddedSeconds}`;
}
