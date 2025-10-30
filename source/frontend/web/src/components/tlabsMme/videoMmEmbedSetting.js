import React, { Component } from 'react';
import { FormField, Input, Select, Container, ColumnLayout, Header, Checkbox } from '@cloudscape-design/components';

class VideoMmEmbeddingSetting extends Component {

    constructor(props) {
        super(props);
        this.state = {
            request: null,
            mmEmbedModel: "twelvelabs.marengo-embed-2-7-v1:0",

            startSec: null,
            lengthSec: null,
            useFixedLengthSec: null,
            minClipSec: null, //Default: 4, Min: 1, Max: 5.
            embedOptionVisualText: true,
            embedOptionVisualImage: true,
            embedOptionAudio: true
        }
    }   

  getRequest() {

    var embedOption = [];
    if (this.state.embedOptionVisualImage)
      embedOption.push("visual-text");
    if (this.state.embedOptionVisualImage)
      embedOption.push("visual-image");
    if (this.state.embedOptionAudio)
      embedOption.push("audio");

    var request = {
      inputType: "video",
      embeddingOption: embedOption
    }
    if (this.state.startSec)
      request["startSec"] = this.state.startSec
    if (this.state.lengthSec)
      request["lengthSec"] = this.state.lengthSec
    if (this.state.useFixedLengthSec)
      request["useFixedLengthSec"] = this.state.useFixedLengthSec
    if (this.state.minClipSec)
      request["minClipSec"] = this.state.minClipSec

    return {
        ModelId: this.state.mmEmbedModel,
        TaskType: "tlabsmmembed",
        TLabsRequest: request
    }
  }

  render() {
    return <div className="embedding">
      <Container header={<Header variant='h3'>TwelveLabs Marengo Embed 2.7 Setting</Header>}>
        <ColumnLayout columns={2}>
          <FormField label="Start Second" description="Start offset in seconds from video start. Leave it empty will start from the beginning.">
            <Input
              onChange={({ detail }) => this.setState({startSec:detail.value})}
              value={parseFloat(this.state.startSec)}
              inputMode="numeric"
              type="number"
            />
          </FormField>
          <FormField label="Length Second" description="The length in seconds of the video where the processing would take from the Start Second. Leave empty to process the video to the end.">
            <Input
              onChange={({ detail }) => this.setState({lengthSec:detail.value})}
              value={parseFloat(this.state.lengthSec)}
              inputMode="numeric"
              type="number"
            />
          </FormField>
        </ColumnLayout>
        <ColumnLayout columns={2}>
          <FormField label="Fix length second" description="Fixed clip duration in seconds (2–10) for embedding. If not set: video is split by shot boundaries.">
            <Input
              onChange={({ detail }) => this.setState({useFixedLengthSec:detail.value})}
              value={parseFloat(this.state.useFixedLengthSec)}
              inputMode="numeric"
              type="number"
            />
          </FormField>
          <FormField label="Minium clip second" description="If a fixed length (in seconds) is specified, it must be greater than this value. Default: 4. Min: 1, Max: 5.">
            <Input
              onChange={({ detail }) => this.setState({minClipSec:detail.value})}
              value={parseInt(this.state.minClipSec)}
              inputMode="numeric"
              type="number"
            />
          </FormField>
        </ColumnLayout>
        <ColumnLayout columns={2}>
          <FormField label="Embedding Options" description="For video only. Specifies embedding types: visual-text, visual-image, or audio.">
            <Checkbox 
              onChange={({ detail }) => this.setState({embedOptionVisualText: detail.checked}) }
              checked={this.state.embedOptionVisualText}
            >visual-text</Checkbox>
            <Checkbox 
              onChange={({ detail }) => this.setState({embedOptionVisualImage: detail.checked}) }
              checked={this.state.embedOptionVisualImage}
            >visual-image</Checkbox>
            <Checkbox 
              onChange={({ detail }) => this.setState({embedOptionAudio: detail.checked}) }
              checked={this.state.embedOptionAudio}
            >audio</Checkbox>
          </FormField>
        </ColumnLayout>
      </Container>
    </div>
  };
};
export default VideoMmEmbeddingSetting;