import React from 'react';
import { FetchPost } from "../../resources/data-provider";
import { 
    Box, 
    ColumnLayout, 
    Container, 
    Header, 
    Spinner, 
    Alert,
    SpaceBetween,
    Badge,
    ExpandableSection
} from '@cloudscape-design/components';
import './dataSize.css';

class DataSize extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            loading: true,
            error: null,
            dataSizeInfo: null,
        };
    }

    async componentDidMount() {
        await this.fetchDataSize();
    }

    async componentDidUpdate(prevProps) {
        if (prevProps.taskId !== this.props.taskId) {
            await this.fetchDataSize();
        }
    }

    async fetchDataSize() {
        this.setState({ loading: true, error: null });
        
        try {
            const data = await FetchPost(
                "/extraction/video/get-data-size",
                { task_id: this.props.taskId },
                "ExtrService"
            );
            
            if (data.statusCode !== 200) {
                this.setState({ 
                    loading: false, 
                    error: data.body?.error || "Failed to fetch data size information" 
                });
            } else {
                this.setState({ 
                    loading: false, 
                    dataSizeInfo: data.body || data,
                    error: null 
                });
            }
        } catch (err) {
            this.setState({ 
                loading: false, 
                error: err.message || "An error occurred while fetching data size" 
            });
        }
    }

    formatBytes(bytes) {
        if (bytes === 0 || bytes === null || bytes === undefined) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatCount(count) {
        if (count === undefined || count === null) return '0';
        return count.toLocaleString();
    }

    getDataTypeDisplayName(type) {
        const typeNames = {
            'video_frame': 'Frame Images',
            'frame_outputs': 'Frame Analysis Outputs',
            'frame_analysis': 'Frame Analysis Results',
            'shot_clip': 'Shot Clips',
            'shot_outputs': 'Shot Analysis Outputs',
            'shot_vector': 'Shot Embeddings',
            'transcribe': 'Audio Transcription',
            'upload': 'Original Video',
            'dynamodb_task_metadata': 'Task Metadata (DynamoDB)',
            'dynamodb_frame_analysis': 'Frame Analysis (DynamoDB)',
            'dynamodb_shot_analysis': 'Shot Analysis (DynamoDB)',
            'dynamodb_transcription': 'Transcription (DynamoDB)',
            'dynamodb_usage_tracking': 'Usage Tracking (DynamoDB)'
        };
        return typeNames[type] || type;
    }

    getDataTypeColor(type) {
        const colors = {
            'video_frame': 'blue',
            'frame_outputs': 'green',
            'frame_analysis': 'green',
            'shot_clip': 'purple',
            'shot_outputs': 'orange',
            'shot_vector': 'red',
            'transcribe': 'grey',
            'upload': 'blue',
            'dynamodb_task_metadata': 'blue',
            'dynamodb_frame_analysis': 'green',
            'dynamodb_shot_analysis': 'orange',
            'dynamodb_transcription': 'grey',
            'dynamodb_usage_tracking': 'red'
        };
        return colors[type] || 'grey';
    }

    renderDataBreakdown() {
        const { dataSizeInfo } = this.state;
        if (!dataSizeInfo || !dataSizeInfo.data_breakdown) return null;

        const breakdown = dataSizeInfo.data_breakdown;
        const totalSize = dataSizeInfo.total_size || 0;

        return (
            <SpaceBetween size="l">
                {/* Total Size */}
                <Container header={<Header variant="h3">Total Generated Data</Header>}>
                    <div className="data-size-card">
                        <div className="data-size-value" style={{ fontSize: '2rem' }}>
                            {this.formatBytes(totalSize)}
                        </div>
                        <div style={{ fontSize: '0.9rem', color: '#5f6b7a', marginTop: '0.5rem' }}>
                            {this.formatCount(dataSizeInfo.total_files)} items across {Object.keys(breakdown).length} data types
                        </div>
                    </div>
                </Container>

                {/* Data Type Breakdown */}
                <ExpandableSection 
                    headerText={`Data Breakdown (${Object.keys(breakdown).length} types)`}
                    defaultExpanded={true}
                >
                    <SpaceBetween size="m">
                        {Object.entries(breakdown).map(([type, info]) => {
                            const percentage = totalSize > 0 ? ((info.size / totalSize) * 100).toFixed(1) : 0;
                            
                            return (
                                <Container key={type} variant="stacked">
                                    <SpaceBetween size="s">
                                        <div className="data-type-header">
                                            <div>
                                                <Badge color={this.getDataTypeColor(type)}>
                                                    {this.getDataTypeDisplayName(type)}
                                                </Badge>
                                                <div style={{ fontSize: '0.85rem', color: '#5f6b7a', marginTop: '0.25rem' }}>
                                                    {type.startsWith('dynamodb_') ? 
                                                        'DynamoDB Table' : 
                                                        `S3 Path: tasks/${this.props.taskId}/${type}/`
                                                    }
                                                </div>
                                            </div>
                                            <div className="data-type-size">
                                                <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>
                                                    {this.formatBytes(info.size)}
                                                </span>
                                                <div style={{ fontSize: '0.8rem', color: '#5f6b7a' }}>
                                                    {percentage}% of total
                                                </div>
                                            </div>
                                        </div>
                                        <ColumnLayout columns={3} variant="text-grid">
                                            <div>
                                                <Box variant="awsui-key-label">{type.startsWith('dynamodb_') ? 'Records' : 'Files'}</Box>
                                                <Box>{this.formatCount(info.file_count)}</Box>
                                            </div>
                                            <div>
                                                <Box variant="awsui-key-label">{type.startsWith('dynamodb_') ? 'Average Record Size' : 'Average File Size'}</Box>
                                                <Box>{info.file_count > 0 ? this.formatBytes(info.size / info.file_count) : '0 B'}</Box>
                                            </div>
                                            <div>
                                                <Box variant="awsui-key-label">{type.startsWith('dynamodb_') ? 'Largest Record' : 'Largest File'}</Box>
                                                <Box>{this.formatBytes(info.max_file_size || 0)}</Box>
                                            </div>
                                        </ColumnLayout>
                                    </SpaceBetween>
                                </Container>
                            );
                        })}
                    </SpaceBetween>
                </ExpandableSection>

                {/* Storage Information */}
                <ExpandableSection 
                    headerText="Storage Information"
                    defaultExpanded={false}
                >
                    <Container>
                        <SpaceBetween size="s">
                            <Alert type="info" header="Data Storage Details">
                                <SpaceBetween size="xs">
                                    <div>
                                        Generated data is stored across two AWS services:
                                    </div>
                                    <ul style={{ marginTop: '0.5rem', paddingLeft: '1.5rem' }}>
                                        <li><strong>Amazon S3:</strong> bedrock-mm-{'{account_id}'}-{'{region}'} (files, images, videos)</li>
                                        <li><strong>Amazon DynamoDB:</strong> Multiple tables for structured data and metadata</li>
                                    </ul>
                                    <div>
                                        <strong>Data Types:</strong>
                                    </div>
                                    <ul style={{ marginTop: '0.5rem', marginBottom: '0.5rem', paddingLeft: '1.5rem' }}>
                                        <li><strong>S3 Storage:</strong></li>
                                        <ul style={{ paddingLeft: '1rem' }}>
                                            <li><strong>Frame Images:</strong> Extracted video frames in image format</li>
                                            <li><strong>Frame Analysis Outputs:</strong> Raw JSON outputs from image understanding models</li>
                                            <li><strong>Shot Clips:</strong> Video segments for shot-based analysis</li>
                                            <li><strong>Shot Analysis Outputs:</strong> Raw JSON outputs from video understanding models</li>
                                            <li><strong>Shot Embeddings:</strong> Vector embeddings for semantic search</li>
                                            <li><strong>Audio Transcription:</strong> Transcription results and metadata</li>
                                        </ul>
                                        <li><strong>DynamoDB Storage:</strong></li>
                                        <ul style={{ paddingLeft: '1rem' }}>
                                            <li><strong>Task Metadata:</strong> Video processing task information and status</li>
                                            <li><strong>Frame Analysis:</strong> Structured frame-level analysis results</li>
                                            <li><strong>Shot Analysis:</strong> Structured shot-level analysis results</li>
                                            <li><strong>Transcription:</strong> Structured transcription data with timestamps</li>
                                            <li><strong>Usage Tracking:</strong> Token usage and cost tracking records</li>
                                        </ul>
                                    </ul>
                                    <div>
                                        <strong>Note:</strong> This data size calculation includes only the additional data generated 
                                        during video processing and does not include the original uploaded video file size.
                                    </div>
                                </SpaceBetween>
                            </Alert>
                        </SpaceBetween>
                    </Container>
                </ExpandableSection>
            </SpaceBetween>
        );
    }

    render() {
        const { loading, error, dataSizeInfo } = this.state;

        if (loading) {
            return (
                <Container header={<Header variant="h2">Data Size</Header>}>
                    <div style={{ textAlign: 'center', padding: '2rem' }}>
                        <Spinner size="large" />
                        <Box variant="p" padding={{ top: 's' }}>Loading data size information...</Box>
                    </div>
                </Container>
            );
        }

        if (error) {
            return (
                <Container header={<Header variant="h2">Data Size</Header>}>
                    <Alert type="warning" header="Unable to load data size information">
                        {error}
                    </Alert>
                </Container>
            );
        }

        if (!dataSizeInfo) {
            return (
                <Container header={<Header variant="h2">Data Size</Header>}>
                    <Alert type="info" header="No data size information available">
                        No data size information found for this task.
                    </Alert>
                </Container>
            );
        }

        return (
            <div className="data-size-container">
                <Container 
                    header={
                        <Header 
                            variant="h2"
                            description="Size of additional data generated during video processing"
                        >
                            Data Size
                        </Header>
                    }
                >
                    {this.renderDataBreakdown()}
                </Container>
            </div>
        );
    }
}

export default DataSize;