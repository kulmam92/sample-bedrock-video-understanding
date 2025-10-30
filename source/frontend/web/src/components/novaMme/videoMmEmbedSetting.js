import React, { Component } from 'react';
import { FormField, Input, Select, Container, ColumnLayout, Header, RadioGroup } from '@cloudscape-design/components';

class VideoMmEmbeddingSetting extends Component {

    constructor(props) {
        super(props);
        this.state = {
            request: null,
            mmEmbedModel: "amazon.nova-2-multimodal-embeddings-v1:0",

            embedMode: "AUDIO_VIDEO_COMBINED",
            duractionS: 5
        }
    }   

  getRequest() {
    return {
        ModelId: this.state.mmEmbedModel,
        EmbedMode: this.state.embedMode,
        DurationS: this.state.duractionS < 1 || this.state.duractionS > 30?5: parseInt(this.state.duractionS)
    }
  }

  render() {
    return <div className="embedding">
      <Container header={<Header variant='h3'>Nova Multi-modal Embedding Setting</Header>}>
        <ColumnLayout columns={2}>
          <FormField label="Embedding Mode">
            <RadioGroup
                onChange={({ detail }) => this.setState({embedMode: detail.value})}
                value={this.state.embedMode}
                items={[
                  { value: "AUDIO_VIDEO_COMBINED", label: "Audio video combined", description: "Will produce a single embedding combing both audible and visual content." },
                  { value: "AUDIO_VIDEO_SEPARATE", label: "Audio video seperated", description: "Will produce a two embeddings, one for the audible content and one for the visual content." },
                ]}
              />
          </FormField>
          <FormField label="Duration (in second)">
            <Input
              onChange={({ detail }) => {
                  this.setState({
                    duractionS:detail.value
                  });
              }}
              value={parseFloat(this.state.duractionS)}
              inputMode="numeric"
              type="number"
              invalid={this.state.duractionS < 1 || this.state.duractionS > 30}
            />
            {(this.state.duractionS < 1 || this.state.duractionS > 30) && 
            <div style={{color:"red", padding: "5px"}}>Please choose a number between 1 and 30</div>}
          </FormField>
        </ColumnLayout>
      </Container>
    </div>
  };
};
export default VideoMmEmbeddingSetting;