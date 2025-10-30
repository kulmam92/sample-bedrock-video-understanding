import React from 'react';
import './agentMain.css'
import { Button, Icon, Tabs } from '@cloudscape-design/components';
import { getCurrentUser } from 'aws-amplify/auth';
import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from "@aws-sdk/client-bedrock-agentcore"; // ES Modules import
import {createAwsClient} from "../../resources/AwsAuth";
import Loading from '../../static/waiting-texting.gif'
import MixedContentDisplay from './mixedContent';
import { nanoid } from 'nanoid';

const SAMPLES = [
    "What are the most common methods used for video analysis?", 
    "Which models on Amazon Bedrock support video analysis?", 
    "I have IP camera/doorbell footage — how should I analyze it to detect theft?",
];

class AgentMain extends React.Component {

    constructor(props) {
        super(props);
        this.state = {
            alert: null,
            items: null,
            userQuery: "",
            selectedItemId: null,
            currentUserName: null,
            refreshSearchTaskId: false,

            chatHistory: [],
            loading: false,

        };
        // Initialize client with config
        this.agentCoreClient = null;
        this.focusRef = React.createRef();
        this.agentCoreSessionId = nanoid(33);

    }
    async componentDidMount() {
        if (this.state.currentUserName === null) {
            const { username } = await getCurrentUser();
            this.setState({currentUserName: username});
        }
        if (this.agentCoreClient === null) {
            this.agentCoreClient = await createAwsClient(BedrockAgentCoreClient);
        }
    }

    componentDidUpdate(prevProps) {
        // Scroll to the bottom whenever messages update
        this.focusRef.current?.scrollIntoView({ behavior: "smooth" });

        if (prevProps.cleanSelectionSignal !== this.props.cleanSelectionSignal) {
            this.setState({selectedItemId: null})
        }
      }

    handleThumbnailClick = (taskId, autoPlay=false) => {
        this.setState({selectedItemId: taskId, autoPlay: autoPlay});
    }

    constructMessage(role, msg) {
        return {
            "role": role,
            "content": [
                {
                    "text": msg
                }
            ]
        }
    }

    handleSubmit = async (e) => {
        try {
            this.setState({ loading: true, error: null, responseText: "" });

            let chatHistory = this.state.chatHistory;
            chatHistory.push(this.constructMessage("user", this.state.userQuery));
            this.setState({chatHistory: chatHistory, userQuery: ""});

            //console.log(chatHistory);
                
            const input = {
                runtimeSessionId: this.agentCoreSessionId,  // Must be 33+ chars
                agentRuntimeArn: process.env.REACT_APP_AGENTCORE_RUNTIME_ARN,
                qualifier: process.env.REACT_APP_AGENTCORE_RUNTIME_ENDPOINT_NAME, // Optional
                payload: new TextEncoder().encode(JSON.stringify(chatHistory)),
            };

            const command = new InvokeAgentRuntimeCommand(input);
            const response = await this.agentCoreClient.send(command);

            if (response.response) {
                // Handle streaming response
                const stream = response.response.transformToWebStream();
                const reader = stream.getReader();
                const decoder = new TextDecoder();

                try {
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        const chunk = decoder.decode(value, { stream: true });
                        //console.log("---------->");
                        //console.log("Chunk received:", chunk);

                        chatHistory = this.state.chatHistory;
                        chatHistory.push(this.constructMessage("assistant", chunk));
                        this.setState({chatHistory: chatHistory, loading: false});

                    }
                    } finally {
                        reader.releaseLock();
                    }
            }
        }
        catch (error) {
            console.log(error);
            
        }
    };

    render() {
        return (
            <div className="agentmain">
                <div className='chatarea'>
                    {this.state.chatHistory && this.state.chatHistory.map((c,i)=>{
                        return <div key={`msg_${i}`} className={`msg${c.role}`}>{  c.role === "assistant"?<MixedContentDisplay content={c.content[0].text}></MixedContentDisplay>:c.content[0].text}</div>
                    })}
                    {this.state.loading && <div className='msgassistant'>
                        <img src={Loading}></img>
                    </div>}
                    <div className='chatbottom' ref={this.focusRef}></div>
                    <div className='input'>
                        <input
                            type="text"
                            className="input-text"
                            placeholder="Ask questions about your videos"
                            onChange={(e)=>{
                                this.setState({userQuery:e.target.value});
                            }}
                            onKeyDown={(e)=>{
                                    if(e.key === "Enter")this.handleSubmit(e);
                                }}
                            value={this.state.userQuery}
                        />
                        <div className='submit'>
                        <Button variant='primary' iconName="arrow-up" 
                            disabled={this.state.userQuery.length === 0}
                            onClick={(e) =>{
                                this.handleSubmit(e);
                            }
                        }></Button>
                        </div>
                    </div>
                    <div className='samples'>
                        <div className='container'>
                        {SAMPLES.map((s,i)=>{
                            return <div key={`sample_${i}`} className='item' onClick={()=> {
                                this.setState({userQuery: s}, () => {this.handleSubmit(null)});}
                            }>{s}</div>;
                        })}
                        </div>
                    </div>
                </div>
                <div className='side'>

                </div>
            </div>
        );
    }
}

export default AgentMain;